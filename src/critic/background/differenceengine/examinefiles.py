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
from typing import (
    Collection,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import diff
from critic import gitaccess
from critic.diff.parse import ExamineResult
from critic.gitaccess import SHA1
from critic.syntaxhighlight.language import identify_language_from_path

from .changedfile import ChangedFile
from .changedlines import ChangedLines
from .job import Job, GroupType


class FileStatus(NamedTuple):
    old: ExamineResult
    new: ExamineResult


class ExamineFiles(Job):
    """Examine files to categorize them as text or binary

    Followed up by CalculateFileDifference for calculating the content
    difference for each modified text file."""

    file_status: Dict[ChangedFile, FileStatus]

    def __init__(
        self,
        group: GroupType,
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
        self.file_status = {}

    def split(self) -> Optional[Collection[ExamineFiles]]:
        if len(self.changed_files) <= 1:
            return None
        return [
            ExamineFiles(
                self.group,
                self.from_commit_sha1,
                self.to_commit_sha1,
                [changed_file],
            )
            for changed_file in self.changed_files
        ]

    async def execute(self) -> None:
        old_paths: Dict[str, None] = {}
        new_paths: Dict[str, None] = {}

        for changed_file in self.changed_files:
            if not changed_file.is_added:
                old_paths[changed_file.path] = None
            if not changed_file.is_removed:
                new_paths[changed_file.path] = None

        async with self.group.repository() as repository:
            if old_paths:
                old_file_status = await diff.parse.examine_files(
                    repository, self.from_commit_sha1, old_paths
                )
            else:
                old_file_status = {}

            if new_paths:
                new_file_status = await diff.parse.examine_files(
                    repository, self.to_commit_sha1, new_paths
                )
            else:
                new_file_status = {}

        logger.debug(
            f"{self.changed_files=} {old_paths=} {old_file_status=} {new_paths=} {new_file_status=}"
        )

        for changed_file in self.changed_files:
            self.file_status[changed_file] = FileStatus(
                old_file_status.get(changed_file.path),
                new_file_status.get(changed_file.path),
            )

    async def update_database(self, critic: api.critic.Critic) -> None:
        """Insert rows into the database table

        One row is inserted into the table 'changesetfiledifferences' for
        each changed file, unconditionally.

        In addition, for files that we won't calculate content differences
        for (added, removed or files changed from binary to text), a single
        row adding or removing all lines is inserted into the table
        'changesetchangedlines'."""

        from .syntaxhighlightfile import syntax_highlight_old, syntax_highlight_new

        def old_is_binary(changed_file: ChangedFile) -> Optional[bool]:
            if changed_file.is_added:
                return None
            if changed_file.old_mode == gitaccess.GIT_LINK_MODE:
                return True
            return self.file_status[changed_file][0] == "binary"

        def new_is_binary(changed_file: ChangedFile) -> Optional[bool]:
            if changed_file.is_removed:
                return None
            if changed_file.new_mode == gitaccess.GIT_LINK_MODE:
                return True
            return self.file_status[changed_file][1] == "binary"

        changesetchangedlines_values: List[
            Tuple[int, Optional[int], Optional[int], Optional[str]]
        ] = []
        highlightfiles_values = []
        old_highlightfile_updates = []
        new_highlightfile_updates = []
        comparison_pending = set()

        def number_of_lines(
            status: ExamineResult, default: Optional[int] = 0
        ) -> Optional[int]:
            return status if isinstance(status, int) else default

        def old_length(changed_file: ChangedFile) -> Optional[int]:
            return number_of_lines(self.file_status[changed_file][0], None)

        def new_length(changed_file: ChangedFile) -> Optional[int]:
            return number_of_lines(self.file_status[changed_file][1], None)

        changeset_id = self.group.changeset_id
        repository_id = self.group.repository_id
        language_ids = self.group.language_ids
        conflicts = self.group.conflicts

        for changed_file in self.changed_files:
            old_status, new_status = self.file_status[changed_file]
            if old_status == 1 and new_status == 1:
                # Modified single-line file (or symbolic link).  No need to ask
                # git which line was modified.  But we will want to have an
                # analysis made, hence None at the end.
                changesetchangedlines_values.append(
                    (changed_file.required_file_id, 1, 1, None)
                )
            # Neither is int: added or removed binary file => needs nothing.
            # One but not both is int: trivial case.
            elif isinstance(old_status, int) != isinstance(new_status, int):
                old_lines = number_of_lines(old_status)
                new_lines = number_of_lines(new_status)
                # Note: Both are zero if we're adding or removing a zero-length
                #       file.  But one must be zero, since we expect to insert
                #       the representation of an added or removed file.
                assert (old_lines == 0) or (new_lines == 0)
                # No need to analyze purely removed or added lines, hence '' at
                # the end.
                changesetchangedlines_values.append(
                    (changed_file.required_file_id, old_lines, new_lines, "")
                )
            # Both are int: modified non-binary file => needs full difference.
            elif isinstance(old_status, int) and isinstance(new_status, int):
                comparison_pending.add(changed_file.file_id)

            language_label = identify_language_from_path(changed_file.path)
            if language_label is not None:
                language_id = language_ids.get_id(language_label)
                if syntax_highlight_old(
                    changed_file.with_status((old_status, new_status))
                ):
                    highlightfiles_values.append(
                        dict(
                            repository_id=repository_id,
                            sha1=changed_file.old_sha1,
                            language_id=language_id,
                            conflicts=conflicts,
                        )
                    )
                    old_highlightfile_updates.append(
                        dict(
                            changeset_id=changeset_id,
                            file_id=changed_file.file_id,
                            repository_id=repository_id,
                            sha1=changed_file.old_sha1,
                            language_id=language_id,
                            conflicts=conflicts,
                        )
                    )
                if syntax_highlight_new(
                    changed_file.with_status((old_status, new_status))
                ):
                    highlightfiles_values.append(
                        dict(
                            repository_id=repository_id,
                            sha1=changed_file.new_sha1,
                            language_id=language_id,
                            conflicts=False,
                        )
                    )
                    new_highlightfile_updates.append(
                        dict(
                            changeset_id=changeset_id,
                            file_id=changed_file.file_id,
                            repository_id=repository_id,
                            sha1=changed_file.new_sha1,
                            language_id=language_id,
                            conflicts=False,
                        )
                    )

        async with critic.transaction() as cursor:
            await cursor.executemany(
                """INSERT
                     INTO changesetfiledifferences (
                            changeset, file, comparison_pending,
                            old_is_binary, old_length,
                            new_is_binary, new_length
                          ) VALUES (
                            {changeset_id}, {file_id}, {comparison_pending},
                            {old_is_binary}, {old_length}, {new_is_binary}, {new_length}
                          )""",
                (
                    dbaccess.parameters(
                        changeset_id=changeset_id,
                        file_id=changed_file.file_id,
                        comparison_pending=changed_file.file_id in comparison_pending,
                        old_is_binary=old_is_binary(changed_file),
                        old_length=old_length(changed_file),
                        new_is_binary=new_is_binary(changed_file),
                        new_length=new_length(changed_file),
                    )
                    for changed_file in self.changed_files
                ),
            )

            await cursor.executemany(
                """INSERT
                     INTO changesetchangedlines (
                            changeset, file, "index", "offset", delete_count,
                            delete_length, insert_count, insert_length,
                            analysis
                          ) VALUES (
                            {changeset_id}, {file_id}, 0, 0, {delete_count},
                            {delete_length}, {insert_count}, {insert_length}, {analysis}
                          )""",
                (
                    dbaccess.parameters(
                        changeset_id=changeset_id,
                        file_id=file_id,
                        delete_count=old_lines,
                        delete_length=old_lines,
                        insert_count=new_lines,
                        insert_length=new_lines,
                        analysis=analysis,
                    )
                    for (
                        file_id,
                        old_lines,
                        new_lines,
                        analysis,
                    ) in changesetchangedlines_values
                ),
            )

            # Insert rows into |highlightfiles| for each file where we determine
            # the language from the filename.
            await cursor.executemany(
                """INSERT
                     INTO highlightfiles (
                            repository, sha1, language, conflicts
                          ) VALUES (
                            {repository_id}, {sha1}, {language_id}, {conflicts}
                          ) ON CONFLICT DO NOTHING""",
                highlightfiles_values,
            )

            for side, updates in (
                ("old", old_highlightfile_updates),
                ("new", new_highlightfile_updates),
            ):
                await cursor.executemany(
                    f"""UPDATE changesetfiledifferences
                           SET {side}_highlightfile=(
                                 SELECT id
                                   FROM highlightfiles
                                  WHERE repository={{repository_id}}
                                    AND sha1={{sha1}}
                                    AND language={{language_id}}
                                    AND conflicts={{conflicts}}
                               )
                         WHERE changeset={{changeset_id}}
                           AND file={{file_id}}""",
                    updates,
                )

    def follow_ups(self) -> Iterable[Job]:
        from .analyzechangedlines import AnalyzeChangedLines
        from .calculatefiledifference import CalculateFileDifference
        from .detectfilelanguages import DetectFileLanguages
        from .syntaxhighlightfile import SyntaxHighlightFile

        need_file_difference = []

        for changed_file in self.changed_files:
            old_status, new_status = self.file_status.get(changed_file, (None, None))
            if old_status or new_status:
                changed_file.set_status((old_status, new_status))
            if not changed_file.modified_regular_file:
                # Only compare modified regular files.
                continue
            # Only one is int: added/removed non-binary file.
            # Neither is int: added or removed binary file.
            if isinstance(old_status, int) and isinstance(new_status, int):
                if old_status > 1 or new_status > 1:
                    need_file_difference.append(changed_file)
                else:
                    # Single-line modified text file.  We optimize away the
                    # actual diffing, but will want an inter-line difference.
                    blocks = [ChangedLines(0, 0, 0, 1, 1, 0, 1, 1)]
                    yield from AnalyzeChangedLines.for_blocks(
                        self.group, changed_file, blocks
                    )

        yield from CalculateFileDifference.for_files(
            self.group,
            self.from_commit_sha1,
            self.to_commit_sha1,
            need_file_difference,
        )

        yield from DetectFileLanguages.for_files(self.group, self.changed_files)

        yield from SyntaxHighlightFile.for_files(self.group, self.changed_files)

    @staticmethod
    def for_files(
        group: GroupType,
        from_commit_sha1: SHA1,
        to_commit_sha1: SHA1,
        changed_files: Sequence[ChangedFile],
    ) -> Iterable[ExamineFiles]:
        CHUNK_SIZE = 100

        for offset in range(0, len(changed_files), CHUNK_SIZE):
            yield ExamineFiles(
                group,
                from_commit_sha1,
                to_commit_sha1,
                changed_files[offset : offset + CHUNK_SIZE],
            )
