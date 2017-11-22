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
from typing import Collection, Iterable, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import changeset
from critic.gitaccess import SHA1, GitTreeEntry
from critic.changeset.structure import ChangedEntry

from .changeset import Changeset
from .changedfile import ChangedFile
from .examinefiles import ExamineFiles
from .job import Job


class CalculateStructureDifference(Job[Changeset]):
    """Calculate the structure difference"""

    def __init__(
        self,
        changeset: Changeset,
        changeset_id: int,
        from_commit_sha1: SHA1,
        to_commit_sha1: SHA1,
        content_difference_requested: bool,
        for_merge: bool,
    ):
        super().__init__(changeset, ())
        self.changeset_id = changeset_id
        self.from_commit_sha1 = from_commit_sha1
        self.to_commit_sha1 = to_commit_sha1
        self.content_difference_requested = content_difference_requested
        self.for_merge = for_merge

    async def execute(self) -> None:
        async with self.group.repository() as repository:
            changed_entries = await changeset.structure.compare_commits(
                repository, self.from_commit_sha1, self.to_commit_sha1
            )

        def sha1(entry: Optional[GitTreeEntry]) -> Optional[SHA1]:
            return None if entry is None else entry.sha1

        def mode(entry: Optional[GitTreeEntry]) -> Optional[int]:
            return None if entry is None else entry.mode

        self.changed_files = [
            ChangedFile(
                None,
                changed_entry.path,
                sha1(changed_entry.old_entry),
                mode(changed_entry.old_entry),
                sha1(changed_entry.new_entry),
                mode(changed_entry.new_entry),
            )
            for changed_entry in changed_entries
        ]

    def referenced_paths(self) -> Collection[str]:
        return set(changed_file.path for changed_file in self.changed_files)

    async def update_database(self, critic: api.critic.Critic) -> None:
        file_ids = self.group.runner.file_ids

        for changed_file in self.changed_files:
            changed_file.file_id = file_ids[changed_file.path]

        async with critic.transaction() as cursor:
            # Faster query, for file ids we have cached.
            await cursor.executemany(
                """INSERT
                     INTO changesetfiles (
                            changeset, file, old_sha1, old_mode, new_sha1, new_mode
                          ) VALUES (
                            {changeset_id}, {file_id}, {old_sha1}, {old_mode},
                            {new_sha1}, {new_mode}
                          )""",
                (
                    dict(
                        changeset_id=self.changeset_id,
                        file_id=changed_file.file_id,
                        old_sha1=changed_file.old_sha1,
                        old_mode=changed_file.old_mode,
                        new_sha1=changed_file.new_sha1,
                        new_mode=changed_file.new_mode,
                    )
                    for changed_file in self.changed_files
                ),
            )

            await cursor.execute(
                """UPDATE changesets
                      SET processed=TRUE,
                          complete={complete}
                    WHERE id={changeset_id}""",
                changeset_id=self.changeset_id,
                complete=not self.for_merge,
            )

    def follow_ups(self) -> Iterable[ExamineFiles]:
        if self.content_difference_requested:
            yield from ExamineFiles.for_files(
                self.group,
                self.from_commit_sha1,
                self.to_commit_sha1,
                self.changed_files,
            )
