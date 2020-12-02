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

from __future__ import annotations

import datetime
import logging
import math
import traceback
from typing import Optional

logger = logging.getLogger("critic.background.branchupdater")

from . import PendingRefUpdateState
from .createbranch import create_branch
from .createreview import create_review
from .deletebranch import delete_branch
from .insertcommits import insert_commits
from .updatebranch import update_branch

from critic import api
from critic import background
from critic import gitaccess
from critic.gitaccess import SHA1
from ...background import githook


class BranchUpdater(background.service.BackgroundService):
    name = "branchupdater"

    def __init__(self) -> None:
        super(BranchUpdater, self).__init__()
        self.preliminary_timeout = getattr(
            self.service_settings, "preliminary_timeout", 30
        )

    async def wake_up(self) -> Optional[float]:
        next_timeout = math.inf
        now = datetime.datetime.now()

        logger.debug("woke up")

        async with self.start_session() as critic:
            async with critic.query(
                """SELECT id, updater, repository, name, old_sha1, new_sha1,
                          state, started_at
                     FROM pendingrefupdates
                    WHERE state='preliminary'"""
            ) as result:
                rows = await result.all()

            for (
                pendingrefupdate_id,
                user_id,
                repository_id,
                ref_name,
                old_sha1,
                new_sha1,
                state,
                started_at,
            ) in rows:
                duration = (now - started_at).total_seconds()
                user = (
                    await api.user.fetch(critic, user_id)
                    if user_id is not None
                    else api.user.system(critic)
                )

                repository = await api.repository.fetch(critic, repository_id)

                try:
                    current_sha1 = await repository.resolveRef(ref_name)
                except api.repository.InvalidRef:
                    current_sha1 = gitaccess.as_sha1("0" * 40)

                if current_sha1 == new_sha1:
                    # The update has been performed by Git, so go ahead and
                    # process it.
                    with critic.asUser(user):
                        await self.handle_update(
                            critic,
                            pendingrefupdate_id,
                            repository,
                            ref_name,
                            old_sha1,
                            new_sha1,
                            state,
                        )
                    # elif duration >= self.preliminary_timeout:
                    #     # The update has timed out.  Probably the git push was
                    #     # aborted before it updated the ref, or Git simply
                    #     # failed/refused to go through with the update.
                    #     self.handle_preliminary_timeout(
                    #         critic, pendingrefupdate_id, user, repository,
                    #         ref_name, old_sha1, new_sha1, current_sha1)
                else:
                    # Make sure we wake up to time the update out.
                    next_timeout = min(
                        next_timeout, max(1, self.preliminary_timeout - duration)
                    )

            async with critic.query(
                """SELECT id, repository, name, old_sha1, new_sha1
                     FROM pendingrefupdates
                    WHERE state='failed'"""
            ) as result:
                async for (
                    pendingrefupdate_id,
                    repository_id,
                    ref_name,
                    old_sha1,
                    new_sha1,
                ) in result:
                    # FIXME: Do something here?
                    pass

        return next_timeout if next_timeout < math.inf else None

    async def handle_preliminary_timeout(
        self,
        critic: api.critic.Critic,
        pendingrefupdate_id: int,
        user: api.user.User,
        repository: api.repository.Repository,
        ref_name: str,
        old_sha1: SHA1,
        new_sha1: SHA1,
        current_sha1: SHA1,
    ) -> None:
        if current_sha1 != old_sha1:
            # Weirdness: We're waiting for a ref to change in one way, and it
            # ends up changing in a different way.  The pre-recieve hook should
            # block all updates of the ref while there is a pending update, so
            # this should not have happened.
            logger.error(
                (
                    "Unexpected ref update in repository '%(repository)s':\n"
                    "  %(ref_name)s changed  %(old_sha1)s..%(current_sha1)s,\n"
                    "  %(padding)s expected %(old_sha1)s..%(new_sha1)s\n"
                )
                % {
                    "repository": repository.name,
                    "ref_name": ref_name,
                    "padding": " " * len(ref_name),
                    "old_sha1": old_sha1[:8],
                    "current_sha1": current_sha1[:8],
                    "new_sha1": new_sha1[:8],
                }
            )
        else:
            logger.info(
                "Update timed out: %s in %s (%s..%s)",
                ref_name,
                repository.name,
                old_sha1[:8],
                new_sha1[:8],
            )

        # Forget about the update.
        async with critic.transaction() as cursor:
            await cursor.execute(
                """DELETE
                     FROM pendingrefupdates
                    WHERE id={pendingrefupdate_id}""",
                pendingrefupdate_id=pendingrefupdate_id,
            )

    async def handle_update(
        self,
        critic: api.critic.Critic,
        pendingrefupdate_id: int,
        repository: api.repository.Repository,
        ref_name: str,
        old_sha1: SHA1,
        new_sha1: SHA1,
        state: PendingRefUpdateState,
    ) -> None:
        logger.debug(
            "Processing update: %s (%s..%s) as %s ...",
            ref_name,
            old_sha1[:8],
            new_sha1[:8],
            critic.effective_user,
        )

        is_review_branch = False
        error = None

        if old_sha1 == "0" * 40:
            action = "creating"
        elif new_sha1 == "0" * 40:
            action = "deleting"
        else:
            action = "updating"

        try:
            if action != "deleting":
                commits = await insert_commits(repository, new_sha1)
            else:
                commits = []

            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name[len("refs/heads/") :]
                is_review_branch = githook.is_review_branch(branch_name)

                if action == "creating":
                    commit = await api.commit.fetch(repository, sha1=new_sha1)
                    if is_review_branch:
                        await create_review(
                            critic,
                            branch_name,
                            commit,
                            pendingrefupdate_id=pendingrefupdate_id,
                        )
                    else:
                        await create_branch(
                            critic,
                            branch_name,
                            commit,
                            commits=commits,
                            pendingrefupdate_id=pendingrefupdate_id,
                        )
                    logger.debug("  created")
                elif action == "deleting":
                    try:
                        branch = await api.branch.fetch(
                            critic, repository=repository, name=branch_name
                        )
                    except api.branch.InvalidName:
                        logger.debug("  missing from database")
                        await githook.set_pendingrefupdate_state(
                            critic, pendingrefupdate_id, "preliminary", "finished"
                        )
                    else:
                        assert not await branch.review
                        await delete_branch(branch, pendingrefupdate_id)
                        logger.debug("  deleted")
                else:
                    branch = await api.branch.fetch(
                        critic, repository=repository, name=branch_name
                    )
                    from_commit, to_commit = await api.commit.fetchMany(
                        repository, sha1s=[old_sha1, new_sha1]
                    )
                    await update_branch(
                        branch,
                        from_commit,
                        to_commit,
                        is_updating_review=branch.type == "review",
                        pendingrefupdate_id=pendingrefupdate_id,
                    )
                    logger.debug("  updated")
            # elif ref_name.startswith("refs/tags/"):
            #     tag_name = ref_name[len("refs/tags/"):]

            #     if action == "creating":
            #         repository.createTag(db, tag_name, new_sha1)
            #     elif action == "deleting":
            #         repository.deleteTag(db, tag_name)
            #     else:
            #         repository.updateTag(db, tag_name, old_sha1, new_sha1)

            logger.info(
                "Processed update: %s in %s (%s..%s)",
                ref_name,
                repository.name,
                old_sha1[:8],
                new_sha1[:8],
            )
        except Exception:
            error = traceback.format_exc()

            await githook.emit_output(
                critic,
                pendingrefupdate_id,
                # FIXME: Refine this error message.
                output="An error occurred while %s %s." % (action, ref_name),
                error=error,
            )

            logger.exception(
                "Update failed: %s (%s..%s)", ref_name, old_sha1[:8], new_sha1[:8]
            )

        async with critic.transaction() as cursor:
            await cursor.execute(
                """UPDATE pendingrefupdates
                      SET state='failed'
                    WHERE id={pendingrefupdate_id}
                      AND state='preliminary'""",
                pendingrefupdate_id=pendingrefupdate_id,
            )


if __name__ == "__main__":
    background.service.call(BranchUpdater)
