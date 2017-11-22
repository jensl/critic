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

import itertools
import logging
import time
from abc import ABC, abstractmethod
from typing import Collection, Generic, Iterable, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess

from . import Key

GroupType = TypeVar("GroupType", bound="JobGroup")


class JobGroup(Generic[GroupType], ABC):
    not_started: Set[job.Job[GroupType]]
    not_started_queue: List[job.Job[GroupType]]
    running: Set[job.Job[GroupType]]
    has_result: Set[job.Job[GroupType]]
    has_traceback: Set[job.Job[GroupType]]
    has_queries: Set[job.Job[GroupType]]
    processed: Set[job.Job[GroupType]]
    failed: Set[Key]
    repository_path: Optional[str]

    def __init__(self, runner: jobrunner.JobRunner, key: Key):
        self.runner = runner
        self.service = runner.service
        self.key = (type(self).__name__,) + key
        self.not_started = set()
        self.not_started_queue = []
        self.running = set()
        self.has_result = set()
        self.has_traceback = set()
        self.has_queries = set()
        self.processed = set()
        self.failed = set()
        self.started = time.time()
        self.timestamp = time.time()
        self.repository_path = None

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, JobGroup) and self.key == other.key

    def __repr__(self) -> str:
        return repr(self.key)

    @property
    def in_progress(self) -> Collection[job.Job[GroupType]]:
        return self.running | self.has_result | self.has_traceback | self.has_queries

    def add_job(self, job: job.Job[GroupType]) -> bool:
        return self.add_jobs(set([job]))

    def add_jobs(self, jobs_iter: Iterable[job.Job[GroupType]], /) -> bool:
        # logger.debug("add_jobs: jobs=%r, failed=%r", jobs, self.failed)
        jobs = set(jobs_iter)
        jobs.difference_update(
            itertools.chain(
                self.not_started, self.in_progress, self.processed, self.failed
            )
        )
        if not jobs:
            return False
        logger.debug("adding %d jobs to: %r", len(jobs), self)
        for added_job in jobs:
            logger.debug("  %r", added_job)
        self.not_started.update(jobs)
        self.not_started_queue = sorted(self.not_started, key=lambda job: job.priority)
        return True

    def get_job_to_start(self) -> Optional[job.Job[GroupType]]:
        if not self.not_started:
            return None
        self.timestamp = time.time()
        job = self.not_started_queue.pop(0)
        self.not_started.remove(job)
        self.running.add(job)
        return job

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    async def calculate_remaining(
        self, critic: api.critic.Critic, initial_calculation: bool = False
    ) -> None:
        ...

    @abstractmethod
    def jobs_finished(self, jobs: Collection[job.Job[GroupType]]) -> None:
        ...

    @abstractmethod
    def group_finished(self) -> None:
        ...

    def repository(self) -> gitaccess.GitRepository:
        assert self.repository_path is not None
        return gitaccess.GitRepository.direct(self.repository_path)


from . import job, jobrunner
