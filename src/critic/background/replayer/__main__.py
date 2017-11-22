# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import logging
import traceback
from typing import Dict, Optional, Tuple

logger = logging.getLogger("critic.background.replayer")

from critic import api
from critic import background
from critic.base import asserted

from .replaymerge import replay_merge
from .replayrebase import replay_rebase

ReplayResult = Optional[Tuple[Optional[int], Optional[str]]]


class Replayer(background.service.BackgroundService):
    name = "replayer"

    __pending_merge_replays: Dict[Tuple[int, int], ReplayResult]
    __pending_rebase_replays: Dict[Tuple[int, int, int], ReplayResult]

    async def did_start(self) -> None:
        self.__pending_merge_replays = {}
        self.__pending_rebase_replays = {}

    async def wake_up(self) -> None:
        async with self.start_session() as critic:
            async with critic.query(
                """SELECT repository, merge
                     FROM mergereplayrequests
                    WHERE replay IS NULL
                      AND traceback IS NULL"""
            ) as result:
                requested_merge_replays = set(await result.all())

            requested_merge_replays.difference_update(self.__pending_merge_replays)

            for repository_id, merge_id in requested_merge_replays:
                merge_key = repository_id, merge_id
                self.__pending_merge_replays[merge_key] = None
                self.run_worker(self.__handle_merge_replay_request(*merge_key))

            finished_merge_replays = {
                key + value
                for key, value in self.__pending_merge_replays.items()
                if value is not None
            }

            async with api.critic.Query[Tuple[int, int, int]](
                critic,
                """SELECT rebase, branchupdate, new_upstream
                     FROM rebasereplayrequests
                    WHERE replay IS NULL
                      AND traceback IS NULL""",
            ) as result:
                requested_rebase_replays = set(await result.all())

            requested_rebase_replays.difference_update(self.__pending_rebase_replays)

            for (
                rebase_id,
                branchupdate_id,
                new_upstream_id,
            ) in requested_rebase_replays:
                rebase_key = (rebase_id, branchupdate_id, new_upstream_id)
                self.__pending_rebase_replays[rebase_key] = None
                self.run_worker(self.__handle_rebase_replay_request(*rebase_key))

            finished_rebase_replays = [
                key + value
                for key, value in self.__pending_rebase_replays.items()
                if value is not None
            ]

            if finished_merge_replays or finished_rebase_replays:
                async with critic.transaction(
                ) as cursor:
                    if finished_merge_replays:
                        await cursor.executemany(
                            """UPDATE mergereplayrequests
                                  SET replay={replay_id},
                                      traceback={traceback}
                                WHERE repository={repository_id}
                                  AND merge={merge_id}""",
                            (
                                dict(
                                    repository_id=repository_id,
                                    merge_id=merge_id,
                                    replay_id=replay_id,
                                    traceback=traceback,
                                )
                                for (
                                    repository_id,
                                    merge_id,
                                    replay_id,
                                    traceback,
                                ) in finished_merge_replays
                            ),
                        )

                    if finished_rebase_replays:
                        await cursor.executemany(
                            """UPDATE rebasereplayrequests
                                  SET replay={replay_id},
                                      traceback={traceback}
                                WHERE rebase={rebase_id}
                                  AND branchupdate={branchupdate_id}
                                  AND new_upstream={new_upstream_id}""",
                            (
                                dict(
                                    rebase_id=rebase_id,
                                    branchupdate_id=branchupdate_id,
                                    new_upstream_id=new_upstream_id,
                                    replay_id=replay_id,
                                    traceback=traceback,
                                )
                                for (
                                    rebase_id,
                                    branchupdate_id,
                                    new_upstream_id,
                                    replay_id,
                                    traceback,
                                ) in finished_rebase_replays
                            ),
                        )

    async def __handle_merge_replay_request(
        self, repository_id: int, merge_id: int
    ) -> None:
        replay_id = stacktrace = None

        try:
            async with self.start_session() as critic:
                repository = await api.repository.fetch(critic, repository_id)
                merge = await api.commit.fetch(repository, merge_id)

                logger.debug("replaying merge: %s", merge.sha1)

                replay = await replay_merge(repository, merge)
                replay_id = replay.id

                logger.debug(
                    "generated merge replay: %s for %s", replay.sha1, merge.sha1
                )
        except Exception:
            logger.exception("Merge replay failed!")
            stacktrace = traceback.format_exc()

        self.__pending_merge_replays[(repository_id, merge_id)] = replay_id, stacktrace
        self.do_wake_up()

    async def __handle_rebase_replay_request(
        self, rebase_id: int, branchupdate_id: int, new_upstream_id: int
    ) -> None:
        replay_id = stacktrace = None

        try:
            async with self.start_session() as critic:
                rebase = await api.log.rebase.fetch(critic, rebase_id)
                review = await rebase.review
                branchupdate = await api.branchupdate.fetch(critic, branchupdate_id)
                new_upstream = await api.commit.fetch(
                    await review.repository, new_upstream_id
                )

                old_upstream = await rebase.as_move_rebase.old_upstream
                old_head = asserted(await branchupdate.from_head)

                logger.debug(
                    "[r/%d] replaying rebase: %s..%s onto %s",
                    review.id,
                    old_upstream.sha1,
                    old_head.sha1,
                    new_upstream.sha1,
                )

                replay = await replay_rebase(
                    rebase.as_move_rebase, branchupdate, new_upstream
                )
                replay_id = replay.id

                logger.debug(
                    "[r/%d] generated rebase replay: %s for %s..%s onto %s",
                    review.id,
                    replay.sha1,
                    old_upstream.sha1,
                    old_head.sha1,
                    new_upstream.sha1,
                )
        except Exception:
            logger.exception("Rebase replay failed!")
            stacktrace = traceback.format_exc()

        self.__pending_rebase_replays[(rebase_id, branchupdate_id, new_upstream_id)] = (
            replay_id,
            stacktrace,
        )
        self.do_wake_up()


if __name__ == "__main__":
    background.service.call(Replayer)
