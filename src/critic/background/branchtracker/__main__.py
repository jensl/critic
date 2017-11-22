# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import asyncio
import functools
import logging
from typing import Dict, Optional, Set, Tuple

logger = logging.getLogger("background.branchtracker")

from critic import api
from critic import background
from critic.base import asserted

from .performupdate import perform_update

# Git (git-send-pack) appends a line suffix to its output.  This suffix depends
# on the $TERM value.  When $TERM is "dumb", the suffix is 8 spaces.  We strip
# this suffix if it's present.  (If we incorrectly strip 8 spaces not actually
# added by Git, it's not the end of the world.)
#
# See https://github.com/git/git/blob/master/sideband.c for details.
DUMB_SUFFIX = "        "


class BranchTrackerService(background.service.BackgroundService):
    name = "branchtracker"

    processing: Set[int]
    reschedule: Dict[int, bool]

    def __init__(self) -> None:
        super().__init__()
        self.processing = set()
        self.reschedule = {}

    def update_done(self, trackedbranch_id: int, task: "asyncio.Future[bool]") -> None:
        self.processing.remove(trackedbranch_id)
        try:
            successful = task.result()
        except Exception:
            logger.exception("Update crashed!")
            successful = False
        self.reschedule[trackedbranch_id] = successful
        self.do_wake_up()

    async def did_start(self) -> None:
        self.processing = set()

    async def start_update(
        self, critic: api.critic.Critic, trackedbranch_id: int
    ) -> "asyncio.Future[bool]":
        trackedbranch = await api.trackedbranch.fetch(critic, trackedbranch_id)
        repository = await trackedbranch.repository
        branch = await trackedbranch.branch

        head_sha1 = (await branch.head).sha1 if branch else None

        return self.run_worker(
            perform_update(
                asserted(repository.low_level.path),
                trackedbranch.source.url,
                trackedbranch.source.name,
                trackedbranch.name,
                head_sha1,
            )
        )

    async def wake_up(self) -> Optional[float]:
        async with self.start_session() as critic:
            # First: Reschedule updates we've just finished. Successful updates
            # are rescheduled according to their configured delay. Failed
            # updates are rescheduled to run again in 15 minutes.
            async with critic.transaction() as cursor:
                await cursor.executemany(
                    """UPDATE trackedbranches
                          SET previous=NOW(),
                              next=NOW() + (
                                CASE WHEN {successful}
                                  THEN delay
                                  ELSE '15 minutes'::interval
                                END
                              )
                        WHERE id={trackedbranch_id}""",
                    [
                        dict(trackedbranch_id=trackedbranch_id, successful=successful)
                        for trackedbranch_id, successful in self.reschedule.items()
                    ],
                )

            # Second: Look for pending updates. This query's result will include
            # any update we're currently working on, which is fine. We'll ignore
            # them below.
            async with api.critic.Query[int](
                critic,
                """SELECT trackedbranches.id
                     FROM trackedbranches
                     JOIN repositories ON (repositories.id=repository)
                    WHERE NOT disabled
                      AND repositories.ready
                      AND (next IS NULL OR next < NOW())
                 ORDER BY next ASC NULLS FIRST""",
            ) as pending_result:
                trackedbranch_ids = await pending_result.scalars()

            # Start pending updates we haven't already started.
            for trackedbranch_id in trackedbranch_ids:
                if trackedbranch_id in self.processing:
                    continue

                (await self.start_update(critic, trackedbranch_id)).add_done_callback(
                    functools.partial(self.update_done, trackedbranch_id)
                )
                self.processing.add(trackedbranch_id)

            # Count number of pending branches, and when the next scheduled
            # update is to be run.
            async with api.critic.Query[Tuple[int, int]](
                critic,
                """SELECT COUNT(*),
                          EXTRACT('epoch' FROM (MIN(next) - NOW()))
                     FROM trackedbranches
                    WHERE NOT disabled
                      AND NOT ({id=processing_ids:array})""",
                processing_ids=list(self.processing),
            ) as status_result:
                pending_branches, update_delay = await status_result.one()

            return update_delay if pending_branches else None


if __name__ == "__main__":
    background.service.call(BranchTrackerService)
