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
from typing import Collection, Dict, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import diff
from critic.gitaccess import SHA1

from .changeset import Changeset
from .changedfile import ChangedFile
from .changedlines import ChangedLines
from .examinefiles import ExamineFiles
from .job import Job


class CalculateFileDifference(Job[Changeset]):
    """Calculate content difference for one changed file

       Followed up by AnalyzeChangedLines for each block of changed lines that
       both deletes and inserts lines."""

    # Sort of redundant: we will never create any CalculateFileDifference jobs
    # until we've examined the files, and we always examine all files with a
    # single job.
    priority = ExamineFiles.priority + 1

    result: Dict[ChangedFile, diff.parse.FileDifference]

    def __init__(
        self,
        group: Changeset,
        from_commit_sha1: SHA1,
        to_commit_sha1: SHA1,
        changed_files: Sequence[ChangedFile],
    ):
        super().__init__(
            group,
            tuple(changed_file.required_file_id for changed_file in changed_files),
        )
        self.from_commit_sha1 = from_commit_sha1
        self.to_commit_sha1 = to_commit_sha1
        self.changed_files = changed_files
        self.result = {}

    async def execute(self) -> None:
        try:
            async with self.group.repository() as repository:
                for changed_file in self.changed_files:
                    self.result[changed_file] = await diff.parse.file_difference(
                        repository,
                        self.from_commit_sha1,
                        self.to_commit_sha1,
                        changed_file.path,
                    )
        except diff.parse.ParseError as error:
            raise Exception("%s: %s" % (changed_file.path, error))

    async def update_database(self, critic: api.critic.Critic) -> None:
        async with critic.transaction() as cursor:
            for (
                changed_file,
                (blocks, old_linebreak, new_linebreak),
            ) in self.result.items():
                await cursor.executemany(
                    """INSERT
                         INTO changesetchangedlines (
                                changeset, file, "index", "offset", delete_count,
                                delete_length, insert_count, insert_length, analysis
                              ) VALUES (
                                {changeset_id}, {file_id}, {index}, {offset},
                                {delete_count}, {delete_length}, {insert_count},
                                {insert_length}, {analysis}
                              )""",
                    (
                        dict(
                            changeset_id=self.group.changeset_id,
                            file_id=changed_file.file_id,
                            index=index,
                            offset=offset,
                            delete_count=delete_count,
                            delete_length=delete_length,
                            insert_count=insert_count,
                            insert_length=insert_length,
                            # Set |analysis| to NULL if analysis is required,
                            # otherwise set to empty string. No analysis is required
                            # for blocksthat only delete or insert lines.
                            analysis=None if (delete_count and insert_count) else "",
                        )
                        for (
                            index,
                            offset,
                            delete_offset,
                            delete_count,
                            delete_length,
                            insert_offset,
                            insert_count,
                            insert_length,
                        ) in blocks
                    ),
                )
                await cursor.execute(
                    """UPDATE changesetfiledifferences
                          SET comparison_pending=FALSE,
                              old_linebreak={old_linebreak},
                              new_linebreak={new_linebreak}
                        WHERE changeset={changeset_id}
                          AND file={file_id}""",
                    changeset_id=self.group.changeset_id,
                    file_id=changed_file.file_id,
                    old_linebreak=old_linebreak,
                    new_linebreak=new_linebreak,
                )

    def split(self) -> Optional[Collection[CalculateFileDifference]]:
        if len(self.changed_files) <= 1:
            return None
        return [
            CalculateFileDifference(
                self.group, self.from_commit_sha1, self.to_commit_sha1, [changed_file],
            )
            for changed_file in self.changed_files
        ]

    def follow_ups(self) -> Iterable[Job[Changeset]]:
        from .analyzechangedlines import AnalyzeChangedLines

        for changed_file, (blocks, old_linebreak, new_linebreak) in self.result.items():
            if not blocks:
                continue
            yield from AnalyzeChangedLines.for_blocks(
                self.group, changed_file, (ChangedLines(*block) for block in blocks)
            )

    @staticmethod
    def for_files(
        group: Changeset,
        from_commit_sha1: SHA1,
        to_commit_sha1: SHA1,
        changed_files: Sequence[ChangedFile],
    ) -> Iterable[CalculateFileDifference]:
        CHUNK_SIZE = 10

        for offset in range(0, len(changed_files), CHUNK_SIZE):
            yield CalculateFileDifference(
                group,
                from_commit_sha1,
                to_commit_sha1,
                changed_files[offset : offset + CHUNK_SIZE],
            )
