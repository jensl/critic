# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import asyncio
import json
import logging
import os
from typing import (
    Any,
    Collection,
    Dict,
    Literal,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)

logger = logging.getLogger("critic.background.githook")

from critic import api
from critic import base
from critic import dbaccess
from critic import gitaccess
from critic import background

from . import (
    Flags,
    RefUpdate,
    ValidateError,
    find_tracked_branch,
    is_review_branch,
    reflow,
)
from .updatehooks import update_hooks
from .validatebranchcreation import validate_branch_creation
from .validatebranchupdate import validate_branch_update
from .validaterefcreation import validate_ref_creation

from ..lineprotocol import LineProtocolClient, LineProtocol


async def getUser(critic: api.critic.Critic, user_name: str) -> api.user.User:
    return await api.user.fetch(critic, name=user_name)


ALLOWED_PATHS = frozenset(
    ["refs/heads/", "refs/tags/", "refs/temporary/", "refs/keepalive/", "refs/roots/"]
)

# Specifically due to restrictions on the 'name' column in the database table
# 'pendingrefupdates' (the 'tags' and 'branches' tables have similar limits),
# but also: insanely long ref names make no sense.
MAXIMUM_REF_NAME_LENGTH = 256

# Number of seconds to wait for a result in the `post-receive` hook.
DEFAULT_POST_RECEIVE_TIMEOUT = 60


def validate_ref_name(ref: RefUpdate) -> Optional[ValidateError]:
    ref_name = ref["ref_name"]
    if len(ref_name) > MAXIMUM_REF_NAME_LENGTH:
        return ValidateError("longer than %d characters" % MAXIMUM_REF_NAME_LENGTH)
    if not ref_name.startswith("refs/"):
        return ValidateError("must start with refs/")
    for allowed_path in ALLOWED_PATHS:
        if ref_name.startswith(allowed_path):
            break
    else:
        parts = ref_name.split("/")
        if len(parts) > 2:
            prefix = "/".join(parts[:2]) + "/"
            return ValidateError("invalid prefix: %s" % prefix)
        else:
            return ValidateError("invalid name")
    if ref_name.startswith("refs/temporary/") or ref_name.startswith("refs/keepalive/"):
        # Ref name must be refs/*/<sha1>.
        sha1 = ref_name[len("refs/keepalive/") :]
        if ref["new_sha1"] != sha1:
            return ValidateError("malformed temporary or keepalive ref")
    return None


async def validate_ref_update(
    repository: api.repository.Repository, ref_name: str
) -> Optional[ValidateError]:
    critic = repository.critic
    user = critic.actual_user

    async with api.critic.Query[Tuple[int, int, str]](
        critic,
        """SELECT id, updater, state
             FROM pendingrefupdates
            WHERE repository={repository_id}
              AND name={ref_name}
              AND state NOT IN ('finished', 'failed')""",
        repository_id=repository.id,
        ref_name=ref_name,
    ) as result:
        try:
            pendingrefupdate_id, updater_id, state = await result.one()
        except dbaccess.ZeroRowsInResult:
            return None

    if state == "finished":
        async with critic.transaction() as cursor:
            await cursor.execute(
                """DELETE
                     FROM pendingrefupdates
                    WHERE id={pendingrefupdate_id}""",
                pendingrefupdate_id=pendingrefupdate_id,
            )
        return None

    if user and updater_id == user.id:
        who = "you"
    else:
        updater = await api.user.fetch(critic, updater_id)
        who = "%s <%s>" % (updater.fullname, updater.email)
    return ValidateError(
        "has pending update",
        f"An update of {ref_name} by {who} is already pending. Please wait a "
        "few seconds, or up to a minute, for the pending update to be "
        "processed or time out.",
    )


async def validate_commits(
    repository: api.repository.Repository, refs: Collection[RefUpdate]
) -> Optional[str]:
    added_sha1s = list(
        set(ref["new_sha1"] for ref in refs if ref["new_sha1"] != "0" * 40)
    )

    # List added root commits.
    added_roots = await repository.low_level.revlist(
        include=added_sha1s, exclude=["--all"], max_parents=0
    )
    if not added_roots:
        return None

    # Typically, adding new root commits is disallowed.  There are two
    # exceptions:
    # - There are no roots in the repository currently.
    # - A single ref named refs/roots/<sha1> is being created, where <sha1> is
    #   the SHA-1 of the added root commit.
    if len(refs) == 1 == len(added_roots) and added_roots[0] in added_sha1s:
        (ref,) = refs
        if ref["ref_name"] == "refs/roots/" + added_roots[0]:
            return None

    try:
        existing_roots = await repository.low_level.revlist(
            include=["--all"], max_parents=0
        )
    except gitaccess.GitProcessError:
        # 'git rev-list --all' fails in an empty repository with no refs in it,
        # since it was given no refs on the command line.
        return None
    else:
        if not existing_roots:
            return None

    if len(added_roots) == 1:
        return f"new root commit added: {added_roots[0]}"
    else:
        return f"{len(added_roots)} new root commits added:\n  " + "\n  ".join(
            added_roots
        )


async def validate_branch_deletion(
    repository: api.repository.Repository, flags: Flags, branch_name: str
) -> Optional[ValidateError]:
    # We don't allow deletion of review branches.
    if is_review_branch(branch_name):
        return ValidateError("%s is a review branch!" % branch_name)

    # We also don't allow deletion (or other updates) of tracked branches.
    trackedbranch = await find_tracked_branch(repository, branch_name)
    if trackedbranch:
        return ValidateError(
            "tracking branch",
            (
                "The branch %s in this repository tracks %s in %s, and should "
                "not be deleted in this repository."
            )
            % (branch_name, trackedbranch.source.name, trackedbranch.source.url),
        )

    return None


def format_error(
    name: Union[str, Sequence[str]], reason: Optional[str], error: ValidateError
) -> str:
    sections = []

    if isinstance(name, str):
        sections.append(f"Rejected ref:\n  {name}")
    else:
        sections.append("Rejected refs:\n  " + "\n  ".join(name))

    if reason is not None:
        sections.append(reflow(f"Reason: {reason}", hanging_indent=2))

    sections.append(reflow(f"Details: {error}", hanging_indent=2))

    if error.message:
        sections.append(reflow(error.message))

    return "\n\n".join(sections)


ClientInput = TypedDict(
    "ClientInput",
    {
        "hook": Literal["pre-receive", "post-receive"],
        "user_name": str,
        "repository_name": str,
        "environ": Dict[str, str],
        "refs": Collection[RefUpdate],
    },
)


class GitHookClient(LineProtocolClient):
    def __init__(
        self,
        settings: Any,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        super().__init__(reader, writer)
        self.settings = settings

    async def respond(
        self,
        output: Optional[Sequence[str]] = None,
        *,
        accept: bool = False,
        reject: bool = False,
        close: Optional[bool] = None,
    ) -> None:
        data: Dict[str, Union[str, bool]] = {}
        if output is not None:
            if not isinstance(output, str):
                output = "".join(output)
            if not output.endswith("..."):
                output += "\n"
            data["output"] = output + "\n"
        if accept:
            data["accept"] = True
        if reject:
            data["reject"] = True
        logger.debug("respond with: %r", data)
        await self.write_line(json.dumps(data))
        if close is None:
            close = accept or reject
        if close:
            await self.close()

    async def handle_line(self, line: str) -> None:
        try:
            data: ClientInput = json.loads(line)

            logger.debug("received data: %r", data)

            system_username = base.configuration()["system.username"]
            user_name: Optional[str] = data["user_name"]
            repository_name = data["repository_name"]
            flags = {}

            if user_name == system_username:
                # Use the REMOTE_USER environment variable (from the environment
                # with which the git hook ran) if present.
                #
                # We use it only if the actual user was the Critic system user,
                # meaning the push was performed by the branch tracker service,
                # the web front-end (for instance via 'git http-backend') or an
                # extension.
                #
                # We also look at the CRITIC_FLAGS environment variable, also
                # only if the actual user was the Critic system user.
                user_name = data["environ"].get("REMOTE_USER")
                flags = json.loads(data["environ"].get("CRITIC_FLAGS", "{}"))

            for_user = user_name is not None

            async with api.critic.startSession(
                for_user=for_user, for_system=not for_user
            ) as critic:
                if for_user:
                    assert user_name
                    await critic.setActualUser(await getUser(critic, user_name))

                repository = await api.repository.fetch(critic, name=repository_name)

                if data["hook"] == "pre-receive":
                    environ = {**repository.low_level.environ}
                    for key, value in data["environ"].items():
                        if key.startswith("GIT_"):
                            environ[key] = value
                    with repository.low_level.with_environ(environ):
                        await self.handle_pre_receive(repository, flags, data["refs"])
                elif data["hook"] == "post-receive":
                    await self.handle_post_receive(repository, flags, data["refs"])
                else:
                    await self.respond(reject=True)
        except Exception:
            await self.respond(
                output="Critic encountered an unexpected error. ¯\\_(ツ)_/¯", reject=True
            )
            raise

    async def handle_pre_receive(
        self,
        repository: api.repository.Repository,
        flags: Flags,
        refs: Collection[RefUpdate],
    ) -> None:
        logger.debug("handle_pre_receive")

        critic = repository.critic

        # First check that all updated refs have valid names.  We only allow
        # refs under some paths under refs/ (see ALLOWED_PREFIXES above.)
        invalid_ref_names = []
        for ref in refs:
            error = validate_ref_name(ref)
            if error:
                invalid_ref_names.append(format_error(ref["ref_name"], None, error))
        if invalid_ref_names:
            await self.respond(output=invalid_ref_names, reject=True)
            return

        # Next check if there's already a pending update for any of the updated
        # refs.
        pending_updates = []
        for ref in refs:
            ref_name = ref["ref_name"]
            pending_update = await validate_ref_update(repository, ref_name)
            if pending_update:
                pending_updates.append(format_error(ref_name, None, pending_update))
        if pending_updates:
            await self.respond(output=pending_updates, reject=True)
            return

        # Next check that would-be created refs can actually be created, or
        # if they conflict with existing refs.
        conflicting_refs = []
        for ref in refs:
            if ref["old_sha1"] == "0" * 40:
                ref_name = ref["ref_name"]
                conflicting_ref_name = await validate_ref_creation(repository, ref_name)
                if conflicting_ref_name:
                    conflicting_refs.append(
                        format_error(
                            ref_name,
                            "conflicts with existing ref",
                            conflicting_ref_name,
                        )
                    )
        if conflicting_refs:
            await self.respond(output=conflicting_refs, reject=True)
            return

        # Next check that the updates add only allowed commits to the
        # repository.  (It's too late, really; the commits will already be in
        # the repository by now, but if we reject ref updates, they'll stay
        # unreferenced an be garbage collected soon.)
        disallowed_commits = await validate_commits(repository, refs)
        if disallowed_commits:
            error = ValidateError(
                disallowed_commits,
                "New root commits can only be pushed to empty repositories, "
                "or by pushing only a ref named `refs/roots/SHA1` where "
                "`SHA1` is the full SHA-1 of the root commit in in question.",
            )
            await self.respond(
                output=format_error([ref["ref_name"] for ref in refs], None, error),
                reject=True,
            )
            return

        # Next perform validations of the actual branch updates.
        invalid_branch_updates = []
        for ref in refs:
            if ref["ref_name"].startswith("refs/heads/"):
                branch_name = ref["ref_name"][len("refs/heads/") :]
                if ref["old_sha1"] == "0" * 40:
                    category = "invalid branch creation"
                    error = await validate_branch_creation(
                        repository, flags, branch_name, ref["new_sha1"]
                    )
                elif ref["new_sha1"] == "0" * 40:
                    category = "invalid branch deletion"
                    error = await validate_branch_deletion(
                        repository, flags, branch_name
                    )
                else:
                    category = "invalid branch update"
                    error = await validate_branch_update(
                        repository, flags, branch_name, ref["old_sha1"], ref["new_sha1"]
                    )
                if error:
                    invalid_branch_updates.append(
                        format_error(branch_name, category, error)
                    )
        if invalid_branch_updates:
            await self.respond(output=invalid_branch_updates, reject=True)
            return

        logger.debug(f"{flags=}")

        # Finally, insert pending update records into the database and wake
        # the branch updater background service up to take note of it.  (It
        # won't do anything right now since it's a preliminary update; it
        # will set a timeout and go back to sleep.)
        async with critic.transaction() as cursor:
            await cursor.executemany(
                """INSERT INTO pendingrefupdates (
                     repository, name, old_sha1, new_sha1, updater, flags
                   ) VALUES (
                     {repository}, {ref_name}, {old_sha1}, {new_sha1}, {updater}, {flags}
                   )""",
                [
                    dict(
                        repository=repository,
                        updater=critic.actual_user,
                        flags=json.dumps(cast(Any, flags)),
                        **ref,
                    )
                    for ref in refs
                ],
            )

        background.utils.wakeup_direct("branchupdater")

        await self.respond(accept=True)

    async def handle_post_receive(
        self,
        repository: api.repository.Repository,
        flags: Flags,
        refs: Collection[RefUpdate],
    ) -> None:
        # This is intentionally quite lenient. In extreme cases the pending ref
        # update could have been deleted already, and we have nothing
        # particularly meaningful to report about that; it's entirely possible
        # everything went alright, just very, very slowly.

        critic = repository.critic
        user = critic.actual_user

        logger.debug("handle_post_receive: %r", user)

        class Update(object):
            def __init__(self, update_id: int, ref_name: str):
                self.update_id = update_id
                self.ref_name = ref_name
                self.status = None
                self.output_seen = -1

            def __repr__(self) -> str:
                return f"<Update id={self.update_id} ref_name={self.ref_name}>"

        updates = {}

        for ref in refs:
            async with critic.query(
                """SELECT id
                     FROM pendingrefupdates
                    WHERE repository={repository}
                      AND name={ref_name}
                      AND old_sha1={old_sha1}
                      AND new_sha1={new_sha1}
                      AND (updater={updater} OR
                           (updater IS NULL AND {is_system}))""",
                repository=repository,
                updater=user,
                is_system=critic.session_type == "system",
                **ref,
            ) as result:
                try:
                    pendingrefupdate_id = await result.scalar()
                except dbaccess.ZeroRowsInResult:
                    logger.warning(
                        "Pending ref missing: %s in %s (%s..%s) for %r",
                        ref["ref_name"],
                        repository.name,
                        ref["old_sha1"][:8],
                        ref["new_sha1"][:8],
                        user,
                    )
                else:
                    updates[pendingrefupdate_id] = Update(
                        pendingrefupdate_id, ref["ref_name"]
                    )

        logger.debug("updates: %r", updates)

        if not updates:
            await self.respond()
            return

        background.utils.wakeup_direct("branchupdater")

        timeout = await repository.getSetting(
            "postReceiveTimeout", DEFAULT_POST_RECEIVE_TIMEOUT
        )

        loop = asyncio.get_running_loop()
        start = loop.time()
        deadline = start + timeout

        send_is_waiting = True

        if len(updates) > 1:
            output_format = "%(ref_name)s:\n\n%(output)s"
        else:
            output_format = "%(output)s"

        sleep_time: float = 0.1
        slept_time: float = 0

        while loop.time() < deadline:
            logger.debug("sleeping %.1f seconds", sleep_time)

            await asyncio.sleep(sleep_time)

            logger.debug("slept %.1f seconds", sleep_time)

            slept_time += sleep_time
            sleep_time = min(sleep_time * 2, 1)

            async with critic.query(
                """SELECT COUNT(*)
                     FROM pendingrefupdates
                    WHERE id=ANY({pendingrefupdate_ids})
                      AND state NOT IN ('finished', 'failed')""",
                pendingrefupdate_ids=list(updates.keys()),
            ) as result:
                remaining = await result.scalar()

            async with critic.query(
                """SELECT pendingrefupdate, id, output
                     FROM pendingrefupdateoutputs
                    WHERE pendingrefupdate=ANY({pendingrefupdate_ids})
                 ORDER BY pendingrefupdate, id""",
                pendingrefupdate_ids=list(updates.keys()),
            ) as result:
                async for update_id, output_id, output in result:
                    update = updates[update_id]
                    if output_id <= update.output_seen:
                        # Already seen.
                        continue
                    await self.respond(
                        output_format
                        % {"ref_name": update.ref_name, "output": output.rstrip()}
                    )
                    update.output_seen = output_id
                    # Skip the "is waiting text" if we've received any output.
                    # It's technically still valid/relevant, but it'll just be
                    # confusing to intermingle it with "regular" output.
                    send_is_waiting = False

            if remaining == 0:
                logger.debug("all finished")
                break

            if send_is_waiting and slept_time >= 1:
                message = (
                    "Waiting for the update%(plural)s to be processed. It is "
                    "safe to stop waiting (e.g. by pressing ctrl-c); the "
                    "update%(plural)s will still be processed."
                ) % {"plural": ("s" if len(updates) > 1 else "")}
                await self.respond(reflow(message))
                send_is_waiting = False
        else:
            # Something appears to have timed out.

            async with api.critic.Query[int](
                critic,
                """SELECT id
                     FROM pendingrefupdates
                    WHERE id=ANY({pendingrefupdate_ids})
                      AND state NOT IN ('finished', 'failed')""",
                pendingrefupdate_ids=list(updates.keys()),
            ) as result:
                timed_out_ids = await result.scalars()

            if timed_out_ids:
                output = "Timed out waiting for Critic to process the update!"

                for update_id in timed_out_ids:
                    update = updates[update_id]
                    await self.respond(
                        output_format % {"ref_name": update.ref_name, "output": output}
                    )

                message = (
                    "Note that the update%(plural)s will continue to be "
                    "processed in the background, and will complete "
                    "eventually, unless something catastrophic has gone "
                    "wrong."
                ) % {"plural": ("s" if len(updates) > 1 else "")}
                await self.respond(reflow(message))

                async with critic.transaction() as cursor:
                    await cursor.execute(
                        """UPDATE pendingrefupdates
                              SET abandoned=TRUE
                            WHERE id=ANY({pendingrefupdate_ids})""",
                        pendingrefupdate_ids=timed_out_ids,
                    )

        revert_branchupdate_ids = []

        async with critic.query(
            """SELECT name, old_sha1, new_sha1, branchupdate
                 FROM pendingrefupdates
                WHERE id=ANY({pendingrefupdate_ids})
                  AND state='failed'""",
            pendingrefupdate_ids=list(updates.keys()),
        ) as result:
            async for ref_name, old_sha1, new_sha1, update_id in result:
                # Revert failed ref update.

                if new_sha1 != "0" * 40:
                    # Make sure the new commits are preserved, to enable
                    # debugging.
                    await repository.low_level.updateref(
                        "refs/keepalive/" + new_sha1, new_value=new_sha1
                    )

                if old_sha1 == "0" * 40:
                    # Ref was created: delete it, so that it can be created
                    # again.
                    await repository.low_level.updateref(
                        ref_name, old_value=new_sha1, delete=True
                    )
                    restored_to = "oblivion"
                elif new_sha1 == "0" * 40:
                    # Ref was deleted: recreate it.
                    await repository.low_level.updateref(ref_name, new_value=old_sha1)
                    restored_to = old_sha1[:8]
                else:
                    # Ref was updated: reset it back to the old value.
                    await repository.low_level.updateref(
                        ref_name, old_value=new_sha1, new_value=old_sha1
                    )
                    restored_to = old_sha1[:8]

                await self.respond(
                    "%s: failed => reset back to: %s" % (ref_name, restored_to)
                )

                if update_id is not None:
                    revert_branchupdate_ids.append(update_id)

        if revert_branchupdate_ids:
            branchupdates = await api.branchupdate.fetchMany(
                critic, revert_branchupdate_ids
            )

            async with api.transaction.start(critic) as transaction:
                for branchupdate in branchupdates:
                    branch = await branchupdate.branch
                    branch_modifier = await transaction.modifyRepository(
                        await branch.repository
                    ).modifyBranch(branch)
                    await branch_modifier.revertUpdate(branchupdate)

        # Delete all finished updates.  Skip ones we just marked as abandoned
        # above, since the user will not have seen the result.
        #
        # If they are finished or failed now, there was a race between the
        # branch/review updater services and us.  No big deal.  Abandoned and
        # finished/failed updates are cleaned up by the branch updater service
        # and the user is notified about any significant results (such as
        # failure.)
        async with critic.transaction() as cursor:
            await cursor.execute(
                """DELETE
                     FROM pendingrefupdates
                    WHERE id=ANY({pendingrefupdate_ids})
                      AND state IN ('finished', 'failed')
                      AND NOT abandoned""",
                pendingrefupdate_ids=list(updates.keys()),
            )

        await self.respond(close=True)


class GitHookService(background.service.BackgroundService, LineProtocol[GitHookClient]):
    name = "githook"

    async def did_start(self) -> None:
        socket_path = self.socket_path()

        if socket_path:
            os.chmod(socket_path, 0o770)

            async with self.start_session() as critic:
                await update_hooks(critic, socket_path)

    def handle_connection(self) -> asyncio.StreamReaderProtocol:
        logger.debug("connection")
        return LineProtocol.handle_connection(self)

    def create_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> GitHookClient:
        return GitHookClient(self.settings, reader, writer)


if __name__ == "__main__":
    background.service.call(GitHookService)
