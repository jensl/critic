# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
import logging
import os
import shutil
import sys
import time
import traceback
from collections import defaultdict
from typing import Dict, List, Tuple

logger = logging.getLogger("critic.background.maintenance")

from .packkeepaliverefs import pack_keepalive_refs

from critic import api
from critic import base
from critic import dbutils
from critic import gitaccess
from critic import background
from critic import pubsub
from critic.api.transaction.protocol import (
    CreatedAPIObject,
    ModifiedAPIObject,
    DeletedRepository,
)


async def run_git_gc(repository: api.repository.Repository) -> None:
    logger.debug("repository GC: %s" % repository.name)
    await pack_keepalive_refs(repository.low_level)
    await repository.low_level.run("gc", "--prune=1 day", "--quiet")


async def create_repository(name: str, path: str) -> bool:
    logger.debug("creating repository %s: %s", name, path)

    repositories_dir = base.configuration()["paths.repositories"]
    executables_dir = base.configuration()["paths.executables"]

    absolute_path = os.path.join(repositories_dir, path)
    parent_dir = os.path.dirname(absolute_path)

    if not os.path.isdir(parent_dir):
        os.makedirs(parent_dir, mode=0o775)

    class Failed(Exception):
        pass

    async def run_git(command: str, *argv: str, **kwargs: str) -> None:
        logger.debug("executing: 'git %s' in %s", " ".join(argv), parent_dir)

        process = await asyncio.create_subprocess_exec(
            gitaccess.git(),
            command,
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=kwargs.get("cwd", absolute_path),
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            loglevel = logging.DEBUG
        else:
            logger.error(
                "'git %s' failed with return code %d", command, process.returncode
            )
            loglevel = logging.ERROR

        if stdout.strip():
            for line in stdout.strip().splitlines():
                logger.log(loglevel, "'git %s' stdout: %s", command, line)

        if stderr.strip():
            for line in stderr.strip().splitlines():
                logger.log(loglevel, "'git %s' stderr: %s", command, line)

        if process.returncode != 0:
            raise Failed()

    try:
        await run_git(
            "init", "--bare", "--shared", os.path.basename(path), cwd=parent_dir
        )
        await run_git("config", "receive.denyNonFastForwards", "false")
        await run_git("config", "critic.name", name)
        await run_git(
            "config", "critic.socket", background.utils.service_address("githook")
        )

        hook_script = os.path.join(executables_dir, "pre-post-receive")
        hooks_dir = os.path.join(absolute_path, "hooks")

        os.symlink(hook_script, os.path.join(hooks_dir, "pre-receive"))
        os.symlink(hook_script, os.path.join(hooks_dir, "post-receive"))
    except Failed:
        return False
    else:
        return True


def delete_repository(name: str, path: str) -> bool:
    logger.debug("deleting repository %s: %s", name, path)

    repositories_dir = base.configuration()["paths.repositories"]

    absolute_path = os.path.join(repositories_dir, path)

    if not os.path.isdir(absolute_path):
        logger.debug(" - directory did not exist: %s", absolute_path)
        return False

    shutil.rmtree(absolute_path)
    return True


class MaintenanceService(background.service.BackgroundService):
    name = "maintenance"
    want_pubsub = True

    async def did_start(self) -> None:
        self.register_maintenance(self.__maintenance, self.service_settings.run_at)

        async with api.critic.startSession(for_system=True) as critic:
            # Do an initial load/update of timezones.
            #
            # The 'timezones' table initially (post-installation) only contains
            # the Universal/UTC timezone; this call adds all the others that the
            # PostgreSQL database server knows about.
            await dbutils.loadTimezones(critic)

    async def handle_created_repository(self, repository_id: int) -> None:
        # Fetch repository details.
        async with self.start_session() as critic:
            async with api.critic.Query[Tuple[str, str, bool]](
                critic,
                """SELECT name, path, ready
                     FROM repositories
                    WHERE id={repository_id}""",
                repository_id=repository_id,
            ) as result:
                name, path, ready = await result.one()

        # Do nothing if it (strangely) already is ready.
        if ready:
            return

        # Perform the actual work.
        await create_repository(name, path)

        # Set the flag that says we created the repository.
        async with self.start_session() as critic:
            repository = await api.repository.fetch(critic, repository_id)
            async with api.transaction.start(critic) as transaction:
                transaction.modifyRepository(repository).setIsReady()

        # Often enough, one or more tracked branches are added directly
        # when a repository is created. The branch tracker will ignore
        # them until the repository is ready, so wake it up now in case
        # it has work to do.
        background.utils.wakeup_direct("branchtracker")

    async def handle_deleted_repository(self, name: str, path: str) -> None:
        if not os.path.isdir(path):
            return

        # Perform the actual work.
        delete_repository(name, path)

    async def handle_message(
        self, channel_name: pubsub.ChannelName, message: pubsub.Message
    ) -> None:
        payload = message.payload
        if isinstance(payload, CreatedAPIObject):
            if payload.resource_name == "repositories":
                await self.handle_created_repository(payload.object_id)
        elif isinstance(payload, DeletedRepository):
            await self.handle_deleted_repository(payload.name, payload.path)

    async def pubsub_connected(self, client: pubsub.Client) -> None:
        logger.debug("pubsub connected")
        await client.subscribe(pubsub.ChannelName("repositories"), self.handle_message)

    async def wake_up(self) -> None:
        logger.debug("woke up")

    async def __maintenance(self) -> None:
        async with api.critic.startSession(for_system=True) as critic:
            # Update the UTC offsets of all timezones.
            #
            # The PostgreSQL database server has accurate (DST-adjusted) values,
            # but is very slow to query, so we cache the UTC offsets in our
            # 'timezones' table.  This call updates that cache every night.
            # (This is obviously a no-op most nights, but we don't want to have
            # to care about which nights it isn't.)
            logger.debug("updating timezones")
            await dbutils.updateTimezones(critic)

            await asyncio.sleep(0)

            # Execute scheduled review branch archivals.
            if self.settings.repositories.archive_review_branches:
                async with critic.query("SELECT NOW()") as result:
                    now = await result.scalar()

                branches_per_repository: Dict[int, List[Tuple[int, str]]] = defaultdict(
                    list
                )

                async with critic.query(
                    """SELECT branches.repository, branches.id,
                              branches.name
                         FROM scheduledreviewbrancharchivals AS srba
                         JOIN reviews ON (reviews.id=srba.review)
                         JOIN branches ON (branches.id=reviews.branch)
                        WHERE srba.deadline <= {now}
                          AND reviews.state IN ('closed', 'dropped')
                          AND NOT branches.archived
                     ORDER BY branches.repository""",
                    now=now,
                    for_update=True,
                ) as result:
                    async for repository_id, branch_id, branch_name in result:
                        branches_per_repository[repository_id].append(
                            (branch_id, branch_name)
                        )

                for repository_id, branches in branches_per_repository.items():
                    repository = await api.repository.fetch(critic, repository_id)

                    logger.info("archiving branches in: " + repository.name)

                    for branch_id, branch_name in branches:
                        logger.info("  " + branch_name)

                        branch = await api.branch.fetch(critic, branch_id)

                        async with api.transaction.start(critic) as transaction:
                            branch_modifier = await transaction.modifyRepository(
                                repository
                            ).modifyBranch(branch)
                            try:
                                await branch_modifier.archive()
                            except Exception:
                                logger.warning(traceback.format_exc())

                async with critic.transaction() as cursor:
                    await cursor.execute(
                        """DELETE
                             FROM scheduledreviewbrancharchivals
                            WHERE deadline <= {now}""",
                        now=now,
                    )

            # Run a garbage collect in all Git repositories, to keep them neat
            # and tidy.  Also pack keepalive refs.
            for repository in await api.repository.fetchAll(critic):
                await run_git_gc(repository)

            if self.settings.extensions.enabled:
                now = time.time()
                max_age = 7 * 24 * 60 * 60

                base_path = os.path.join(
                    base.configuration()["paths.home"],
                    self.settings.extensions.workcopy_dir,
                )

                for user_name in os.listdir(base_path):
                    user_dir = os.path.join(base_path, user_name)

                    for extension_id in os.listdir(user_dir):
                        extension_dir = os.path.join(user_dir, extension_id)

                        for repository_name in os.listdir(extension_dir):
                            repository_dir = os.path.join(
                                extension_dir, repository_name
                            )
                            age = now - os.stat(repository_dir).st_mtime

                            if age > max_age:
                                logger.info(
                                    "Removing repository work copy: %s", repository_dir
                                )
                                shutil.rmtree(repository_dir)
                                await asyncio.sleep(0)


if __name__ == "__main__":
    background.service.call(MaintenanceService)
