from __future__ import annotations

import asyncio
import logging
import multiprocessing
import time
import traceback
from collections import defaultdict
from typing import (
    Any,
    AsyncContextManager,
    Awaitable,
    Dict,
    Optional,
    Protocol,
    Sequence,
    Set,
    TypeVar,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import syntaxhighlight
from critic import pubsub

from . import Key
from .languageids import LanguageIds
from .fileids import FileIds
from .changeset import Changeset
from .customhighlight import CustomHighlight
from .requestjob import RequestJob
from .job import Job, GroupType, RunnerType
from .jobgroup import JobGroup


class Pool:
    running: Dict[Key, "asyncio.Future[None]"]

    def __init__(self, runner: JobRunner, parallel_jobs: Optional[int] = None):
        self.runner = runner
        if parallel_jobs is None:
            parallel_jobs = multiprocessing.cpu_count()
        self.parallel_jobs = parallel_jobs
        self.running = {}

    def start_job(self, job_to_start: Job) -> None:
        async def run_job() -> None:
            job_to_start.signal_started()
            try:
                await job_to_start.execute()
            except Exception as error:
                job_to_start.signal_failure(error, traceback.format_exc())
                await self.runner.job_failed(job_to_start)
            else:
                if isinstance(job_to_start, RequestJob) and job_to_start.requests:
                    self.runner.register_requests(
                        cast(RequestJob[Any], job_to_start), job_to_start.requests
                    )
                else:
                    job_to_start.signal_success()
                    await self.runner.job_finished(cast(RequestJob[Any], job_to_start))

        def finished(future: "asyncio.Future[None]") -> None:
            del self.running[job_to_start.key]

        future = self.running[job_to_start.key] = asyncio.ensure_future(run_job())
        future.add_done_callback(finished)

    @property
    def has_available_slot(self) -> bool:
        return self.parallel_jobs > len(self.running)


T = TypeVar("T")


class Service(Protocol):
    @property
    def settings(self) -> Any:
        ...

    @property
    def service_settings(self) -> Any:
        ...

    @property
    async def pubsub_client(self) -> pubsub.Client:
        ...

    def start_session(self) -> AsyncContextManager[api.critic.Critic]:
        ...

    def check_future(self, coro: Awaitable[T]) -> "asyncio.Future[T]":
        ...

    def monitor_changeset(self, changeset_id: int) -> None:
        ...

    def update_changeset(self, changeset_id: int) -> None:
        ...

    def forget_changeset(self, changeset_id: int) -> None:
        ...


class JobRunner(RunnerType):
    all_groups: Set[JobGroup]
    finished_jobs: Set[Job]
    failed_jobs: Set[Job]
    requests: Set[pubsub.OutgoingRequest]

    def __init__(self, service: Service):
        self.__service = service

        # Set to true by the main thread to stop us.
        self.terminated = False
        # Set to true before we stop (whether asked to or not.)
        self.stopped = False
        self.db = None
        self.pool = Pool(self, service.service_settings.parallel_jobs)
        # self.query_queue = UpdatingQueryQueue(self)

        self.condition = asyncio.Condition()
        # The containers below are protected by the condition above.
        self.all_groups = set()
        self.finished_jobs = set()
        self.failed_jobs = set()
        # Set to true by the main thread when it has been signalled, meaning we
        # should look for new changesets to work on.
        self.signalled = True
        # Set to true when something changes so that a find_incomplete() might
        # find new things.
        self.__find_new_incomplete = False

        # Function to call when we reach an idle state.
        # self.idle_callback = None
        self.requests = set()

        syntaxhighlight.language.setup()

    @property
    def service(self) -> Service:
        return self.__service

    @property
    def language_ids(self) -> LanguageIds:
        return self.__language_ids

    @property
    def file_ids(self) -> FileIds:
        return self.__file_ids

    def find_new_incomplete(self) -> None:
        self.__find_new_incomplete = True

    async def run_jobs(self) -> None:
        while True:
            if self.terminated:
                logger.debug("job runner: was terminated")
                break

            self.signalled = False

            group: GroupType

            # Start new jobs, if possible.
            while self.pool.has_available_slot:
                for group in sorted(self.all_groups, key=lambda group: group.timestamp):
                    job = group.get_job_to_start()
                    if job:
                        logger.debug("job runner: starting job: %r", job)
                        self.pool.start_job(job)
                        break
                else:
                    # No more jobs to start.
                    break

            # Process finished jobs.
            if self.finished_jobs:
                finished_jobs = list(self.finished_jobs)
                self.finished_jobs.clear()

                added_follow_ups = False
                referenced_paths: Set[str] = set()

                for job in finished_jobs:
                    referenced_paths.update(job.referenced_paths())

                # Ensure all referenced paths exist in the |files| table and in
                # the file id cache.

                async with self.service.start_session() as critic:
                    await self.file_ids.ensure_paths(critic, referenced_paths)

                    per_group: Dict[GroupType, Set[Job]] = defaultdict(set)

                    for job in finished_jobs:
                        logger.debug(
                            "job runner: finishing job: %s (%.2f ms)"
                            % (job, 1000 * (job.finished - job.started))
                        )
                        per_group[job.group].add(job)
                        try:
                            follow_ups = await job.process_result(critic)
                            if follow_ups:
                                logger.debug(
                                    "job runner: adding %d follow-ups" % len(follow_ups)
                                )
                                job.group.add_jobs(follow_ups)
                                added_follow_ups = True
                        except Exception as error:
                            logger.exception(
                                "job runner: failed to finish job: %r", job
                            )
                            # This will move the job over to |group.has_traceback|,
                            # and the group over to |updated_groups|.
                            job.signal_failure(error, traceback.format_exc())

                    for group, jobs in per_group.items():
                        for job in jobs:
                            group.running.remove(job)
                        group.processed.update(jobs)
                        group.jobs_finished(jobs)

                if added_follow_ups:
                    continue

            # Process failed jobs.
            if self.failed_jobs:
                failed_jobs = list(self.failed_jobs)
                self.failed_jobs.clear()

                async with self.service.start_session() as critic:
                    for job in failed_jobs:
                        logger.debug("job runner: failed job: %r", job)
                        partial_jobs = await job.process_traceback(critic)
                        if partial_jobs:
                            job.group.add_jobs(set(partial_jobs))

            # Find groups with no pending or in-progress jobs.
            new_jobs = False
            async with self.service.start_session() as critic:
                for group in list(self.all_groups):
                    # logger.debug(
                    #     "%r: not_started=%r, in_progress=%r",
                    #     group,
                    #     group.not_started,
                    #     group.in_progress,
                    # )
                    if not (group.not_started or group.in_progress):
                        # Recalculate remaining jobs.  May find new stuff now,
                        # or have other side-effects.
                        await group.calculate_remaining(critic)
                        if group.not_started:
                            new_jobs = True
                        else:
                            # No new pending jobs were added => this group is
                            # finished.
                            self.all_groups.remove(group)
                            group.group_finished()
                            elapsed = time.time() - group.started
                            logger.info(
                                "%s finished in %.2f s (%d jobs)",
                                group,
                                elapsed,
                                len(group.processed),
                            )
            if new_jobs:
                # New jobs found.  Jump to the top to start them ASAP.
                continue

            if self.__find_new_incomplete:
                self.__find_new_incomplete = False

                incomplete_groups: Set[JobGroup] = set()
                async with self.service.start_session() as critic:
                    incomplete_groups.update(
                        await Changeset.find_incomplete(critic, self)
                    )
                    incomplete_groups.update(
                        await CustomHighlight.find_incomplete(critic, self)
                    )
                    if incomplete_groups:
                        incomplete_groups -= self.all_groups
                        if incomplete_groups:
                            for group in incomplete_groups:
                                logger.debug("starting group: %r", group)
                                group.start()
                                await group.calculate_remaining(
                                    critic, initial_calculation=True
                                )
                            self.all_groups.update(incomplete_groups)
                            if self.pool.has_available_slot:
                                # Jump to the top to start new jobs ASAP.
                                continue

            def something_to_do() -> bool:
                logger.debug(
                    "something_do_do(): terminated=%r, signalled=%r, "
                    "find_new_incomplete=%r, finished_jobs=%d, failed_jobs=%d",
                    self.terminated,
                    self.signalled,
                    self.__find_new_incomplete,
                    len(self.finished_jobs),
                    len(self.failed_jobs),
                )
                return bool(
                    self.terminated
                    or self.signalled
                    or self.__find_new_incomplete
                    or self.finished_jobs
                    or self.failed_jobs
                )

            if something_to_do():
                continue

            if not self.all_groups:
                logger.debug("job runner: idle")
                # if self.idle_callback:
                #     self.idle_callback()
                #     self.idle_callback = None
            else:
                logger.debug(
                    "job runner: waiting"
                    " (%d active groups, %d running jobs, %d pending requests)"
                    % (len(self.all_groups), len(self.pool.running), len(self.requests))
                )

            async with self.condition:
                await self.condition.wait_for(something_to_do)

            if self.signalled:
                logger.debug("job runner: signalled")
            else:
                logger.debug("job runner: notified")

    async def run(self) -> None:
        self.__language_ids = LanguageIds()
        self.__file_ids = FileIds()

        async with self.service.start_session() as critic:
            await self.language_ids.update(
                critic, self.service.settings.syntax.languages
            )
            await self.file_ids.update(critic)

        try:
            await self.run_jobs()
        except Exception:
            logger.exception("job runner: crashed!")

    def register_requests(
        self, job: RequestJob[Any], requests: Sequence[pubsub.OutgoingRequest]
    ) -> None:
        logger.debug("register_requests: job=%r, requests=%r", job, requests)

        self.requests.update(requests)

        async def wait() -> None:
            responses = await asyncio.gather(
                *(request.response for request in requests), return_exceptions=True
            )
            self.requests -= set(requests)
            job.responses = responses
            for response in responses:
                if isinstance(response, Exception):
                    job.signal_failure(response)
                    await self.job_failed(job)
                    break
            else:
                job.signal_success()
                await self.job_finished(job)

        self.service.check_future(wait())

    async def job_finished(self, job: Job) -> None:
        async with self.condition:
            self.finished_jobs.add(job)
            self.condition.notify()

    async def job_failed(self, job: Job) -> None:
        async with self.condition:
            self.failed_jobs.add(job)
            self.condition.notify()

    async def new_changesets(self) -> None:
        logger.debug("new_changesets()")
        async with self.condition:
            self.__find_new_incomplete = True
            self.condition.notify()

    async def signal(self) -> None:
        async with self.condition:
            self.signalled = True
            self.condition.notify()

    async def terminate(self) -> None:
        async with self.condition:
            self.terminated = True
            self.condition.notify()
