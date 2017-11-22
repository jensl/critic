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
from typing import Collection, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic.gitaccess import SHA1

from .job import Job
from .jobgroup import JobGroup


class CustomHighlight(JobGroup["CustomHighlight"]):
    def __init__(
        self,
        runner: jobrunner.JobRunner,
        request_id: int,
        repository_id: int,
        file_id: int,
    ):
        super().__init__(runner, key=(request_id, repository_id))
        self.request_id = request_id
        self.repository_id = repository_id
        self.file_id = file_id
        self.conflicts = False
        self.language_ids = runner.language_ids

    def __str__(self) -> str:
        return "custom highlight %d" % self.request_id

    def start(self) -> None:
        logger.debug("%s: starting", self)

    async def calculate_remaining(
        self, critic: api.critic.Critic, initial_calculation: bool = False
    ) -> None:
        from .syntaxhighlightfile import SyntaxHighlightFile

        if initial_calculation:
            async with api.critic.Query[str](
                critic,
                """SELECT path
                     FROM repositories
                    WHERE id={repository_id}""",
                repository_id=self.repository_id,
            ) as repository_path:
                self.repository_path = await repository_path.scalar()

        async with api.critic.Query[Tuple[SHA1, str, bool]](
            critic,
            """SELECT sha1, label, conflicts
                 FROM highlightfiles
                 JOIN highlightlanguages ON (language=highlightlanguages.id)
                WHERE highlightfiles.id={file_id}
                  AND requested""",
            file_id=self.file_id,
        ) as highlight_files:
            jobs = {
                SyntaxHighlightFile(self, sha1, language_label, conflicts)
                async for sha1, language_label, conflicts in highlight_files
            }

        self.add_jobs(jobs)

    def jobs_finished(self, jobs: Collection[Job[CustomHighlight]]) -> None:
        # Publish a message to notify interested parties about the
        # updated completion level.
        logger.debug("%s: %d jobs_finished", self, len(jobs))

    def group_finished(self) -> None:
        logger.debug("%s: finished", self)

    @staticmethod
    async def find_incomplete(
        critic: api.critic.Critic, runner: jobrunner.JobRunner
    ) -> Collection[CustomHighlight]:
        async with api.critic.Query[Tuple[int, int, int]](
            critic,
            """SELECT DISTINCT customhighlightrequests.id,
                               customhighlightrequests.file,
                               highlightfiles.repository
                 FROM customhighlightrequests
                 JOIN highlightfiles ON (
                        highlightfiles.id=customhighlightrequests.file
                      )
                WHERE highlightfiles.requested""",
        ) as result:
            return {
                CustomHighlight(runner, request_id, repository_id, file_id)
                async for request_id, file_id, repository_id in result
            }


from . import jobrunner
