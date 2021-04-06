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
from typing import (
    Any,
    Collection,
    Iterable,
    List,
    Optional,
    Set,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess

from . import Key
from .job import ChangesetGroupType, Job, RunnerType, ServiceType
from .requestjob import RequestJob
from .languageids import LanguageIds


class JobGroup(ABC):
    not_started: Set[Job]
    not_started_queue: List[Job]
    __running: Set[Job]
    has_result: Set[Job]
    has_traceback: Set[Job]
    has_queries: Set[Job]
    __processed: Set[Job]
    failed: Set[Key]
    decode: api.repository.Decode

    def __init__(self, runner: RunnerType, key: Key, repository_id: int):
        self.__runner = runner
        self.__key = (type(self).__name__,) + key
        self.__repository_id = repository_id
        self.not_started = set()
        self.not_started_queue = []
        self.__running = set()
        self.has_result = set()
        self.has_traceback = set()
        self.has_queries = set()
        self.__processed = set()
        self.failed = set()
        self.started = time.time()
        self.timestamp = time.time()

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, JobGroup) and self.key == other.key

    def __repr__(self) -> str:
        return repr(self.key)

    @property
    def runner(self) -> RunnerType:
        return self.__runner

    @property
    def service(self) -> ServiceType:
        return self.__runner.service

    @property
    def language_ids(self) -> LanguageIds:
        return self.__runner.language_ids

    @property
    def key(self) -> Key:
        return self.__key

    @property
    def running(self) -> Set[Job]:
        return self.__running

    @property
    def processed(self) -> Set[Job]:
        return self.__processed

    @property
    def in_progress(self) -> Collection[Job]:
        return self.running | self.has_result | self.has_traceback | self.has_queries

    def add_job(self, job: Job) -> bool:
        return self.add_jobs(set([job]))

    def add_jobs(self, jobs_iter: Iterable[Job], /) -> bool:
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
        self.not_started_queue = sorted(
            filter(lambda job: not isinstance(job, RequestJob), self.not_started),
            key=lambda job: job.priority,
        )
        return True

    def get_job_to_start(self) -> Optional[Job]:
        if not self.not_started_queue:
            return None
        self.timestamp = time.time()
        job = self.not_started_queue.pop(0)
        self.not_started.remove(job)
        self.running.add(job)
        return job

    def get_request_jobs(self) -> Collection[RequestJob[Any]]:
        request_jobs = set()
        for job in self.not_started:
            if isinstance(job, RequestJob):
                request_jobs.add(cast(RequestJob[Any], job))
        self.not_started.difference_update(request_jobs)
        self.running.update(request_jobs)
        return request_jobs

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    async def calculate_remaining(
        self, critic: api.critic.Critic, initial_calculation: bool = False
    ) -> None:
        ...

    @abstractmethod
    def jobs_finished(self, jobs: Collection[Job]) -> None:
        ...

    @abstractmethod
    async def process_traceback(self, critic: api.critic.Critic, job: Job) -> None:
        ...

    @abstractmethod
    def group_finished(self) -> None:
        ...

    @property
    def repository_id(self) -> int:
        return self.__repository_id

    @property
    @abstractmethod
    def repository_path(self) -> str:
        ...

    def repository(self) -> gitaccess.GitRepository:
        return gitaccess.GitRepository.direct(self.repository_path)

    @property
    @abstractmethod
    def as_changeset(self) -> ChangesetGroupType:
        ...
