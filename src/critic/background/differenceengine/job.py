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

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Collection, Generic, Iterable, Optional, Sequence, TypeVar

logger = logging.getLogger(__name__)

from critic import api

from . import serialize_key, Key

JobType = TypeVar("JobType", bound="Job")
GroupType = TypeVar("GroupType", bound="jobgroup.JobGroup")


class Job(Generic[GroupType], ABC):
    # Higher values => lower priority.  Jobs with higher priority are
    # unconditionally started before jobs with lower priority.
    #
    # Note: Job priority only affects the order in which jobs in a group are
    # started.  A job with low priority in one group can be started despite
    # there being a job with a higher priority in another group.
    priority = 0

    # Stored in |changeseterrors.fatal| if the job failed.  If true, the
    # whole content difference is considered useless.  If false, the error is
    # reported to the system administrator, while the user sees a useble but
    # probably less that optimal view.
    is_fatal = True

    error: Optional[Exception]
    traceback: Optional[str]
    __started: Optional[float]
    __finished: Optional[float]

    def __init__(self, group: GroupType, key: Key):
        self.group = group
        self.runner = group.runner
        self.service = group.service
        self.key = (type(self).__name__,) + group.key + key
        self.error = self.traceback = None
        self.__started = self.__finished = None

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return self.key == other

    def __str__(self) -> str:
        return self.key[0]

    def __repr__(self) -> str:
        return repr(self.key)

    @property
    def started(self) -> float:
        assert self.__started is not None
        return self.__started

    @property
    def finished(self) -> float:
        assert self.__finished is not None, repr(self)
        return self.__finished

    def signal_started(self) -> None:
        self.__started = time.time()

    def signal_success(self) -> None:
        self.__finished = time.time()

    def signal_failure(self, error: Exception, traceback: str = "N/A") -> None:
        self.__finished = time.time()
        self.error = error
        self.traceback = traceback

    def referenced_paths(self) -> Collection[str]:
        return set()

    @abstractmethod
    async def execute(self) -> None:
        ...

    async def update_database(self, critic: api.critic.Critic) -> None:
        pass

    def follow_ups(self) -> Iterable[Job[GroupType]]:
        return set()

    def split(self: JobType) -> Optional[Collection[JobType]]:
        return None

    async def process_result(
        self, critic: api.critic.Critic
    ) -> Collection[Job[GroupType]]:
        await self.update_database(critic)
        return set(self.follow_ups())

    async def process_traceback(
        self, critic: api.critic.Critic
    ) -> Optional[Collection[Job[GroupType]]]:
        assert self.error is not None and self.traceback is not None

        logger.error(
            "Failed job: %r\n%s\nTraceback:\n  %s",
            self.key,
            self.error,
            self.traceback.strip(),
        )

        partial_jobs = self.split()
        if partial_jobs:
            # Split the job into smaller parts, to pin-point the part that
            # actually failed.
            return partial_jobs

        if isinstance(self.group, changeset.Changeset):
            async with critic.transaction() as cursor:
                await cursor.execute(
                    """INSERT INTO changeseterrors (
                        changeset, job_key, fatal, traceback
                    ) VALUES (
                        {changeset}, {job_key}, {fatal}, {traceback}
                    )""",
                    changeset=self.group.changeset_id,
                    job_key=serialize_key(self.key),
                    fatal=self.is_fatal,
                    traceback=self.traceback,
                )

        return None


from . import jobgroup, changeset
