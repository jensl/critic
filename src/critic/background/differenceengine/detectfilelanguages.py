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
from dataclasses import dataclass

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
from critic.dbaccess import Parameters
from critic.gitaccess import SHA1

from .changedfile import ChangedFile
from .job import Job, GroupType
from .syntaxhighlightfile import (
    SyntaxHighlightFile,
    syntax_highlight_old,
    syntax_highlight_new,
)

from ...syntaxhighlight.language import (
    setup,
    identify_language_from_source,
    identify_language_from_path,
)


class Language(NamedTuple):
    label: str
    id: int


@dataclass
class FileVersion:
    changed_file: ChangedFile
    sha1: SHA1
    conflicts: bool
    decode: api.repository.Decode


class DetectFileLanguages(Job):
    # Detect file languages quite soon.
    priority = 1  # ExamineFiles.priority + 1

    # Failure to syntax highlight a file is non-fatal; we can just display a
    # non-highlighted version of the file.
    is_fatal = False

    result_type = (type(None), str)

    language_by_sha1: Dict[SHA1, Language]

    def __init__(self, group: GroupType, file_versions: Sequence[FileVersion]):
        super().__init__(
            group,
            tuple(
                file_version.changed_file.required_file_id
                for file_version in file_versions
            ),
        )
        self.file_versions = file_versions
        self.language_by_sha1 = {}

    def split(self) -> Optional[Collection[DetectFileLanguages]]:
        if len(self.file_versions) <= 1:
            return None
        return [
            DetectFileLanguages(self.group, [file_version])
            for file_version in self.file_versions
        ]

    async def execute(self) -> None:
        setup()

        from_source_sha1s: List[FileVersion] = []

        for file_version in self.file_versions:
            label = identify_language_from_path(file_version.changed_file.path)
            if label is not None:
                language_id = self.group.language_ids.get_id(label)
                if language_id is not None:
                    self.language_by_sha1[file_version.sha1] = Language(
                        label, language_id
                    )
            else:
                from_source_sha1s.append(file_version)

        if from_source_sha1s:
            async with self.group.repository() as repository:
                for file_version in from_source_sha1s:
                    label = await identify_language_from_source(
                        repository,
                        file_version.sha1,
                        file_version.decode.fileContent(file_version.changed_file.path),
                    )
                    if label is not None:
                        language_id = self.group.language_ids.get_id(label)
                        if language_id is not None:
                            self.language_by_sha1[file_version.sha1] = Language(
                                label, language_id
                            )

    async def update_database(self, critic: api.critic.Critic) -> None:
        changeset_id = self.group.as_changeset.changeset_id
        repository_id = self.group.repository_id
        async with critic.transaction() as cursor:
            await cursor.executemany(
                """INSERT
                     INTO highlightfiles (
                            repository, sha1, language, conflicts
                          ) VALUES (
                            {repository_id}, {sha1}, {language_id}, {conflicts}
                          ) ON CONFLICT DO NOTHING""",
                (
                    dbaccess.parameters(
                        repository_id=repository_id,
                        sha1=file_version.sha1,
                        language_id=self.language_by_sha1[file_version.sha1].id,
                        conflicts=file_version.conflicts,
                    )
                    for file_version in self.file_versions
                    if file_version.sha1 in self.language_by_sha1
                ),
            )

            old_highlightfile_updates: List[Parameters] = []
            new_highlightfile_updates: List[Parameters] = []

            for file_version in self.file_versions:
                if file_version.sha1 not in self.language_by_sha1:
                    continue
                if file_version.sha1 == file_version.changed_file.old_sha1:
                    updates = old_highlightfile_updates
                else:
                    updates = new_highlightfile_updates
                updates.append(
                    dict(
                        changeset_id=changeset_id,
                        file_id=file_version.changed_file.file_id,
                        repository_id=repository_id,
                        sha1=file_version.sha1,
                        language_id=self.language_by_sha1[file_version.sha1].id,
                        conflicts=file_version.conflicts,
                    )
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

    # def follow_ups(self) -> Iterable[SyntaxHighlightFile]:
    #     for file_version in self.file_versions:
    #         language = self.language_by_sha1.get(file_version.sha1)
    #         if language is None:
    #             continue
    #         yield SyntaxHighlightFile(
    #             self.group,
    #             file_version.sha1,
    #             language.label,
    #             file_version.conflicts,
    #             file_version.decode.getFileContentEncodings(
    #                 file_version.changed_file.path
    #             ),
    #         )

    @staticmethod
    def for_files(
        group: GroupType,
        changed_files: Iterable[ChangedFile],
        *,
        skip_file_versions: Collection[Tuple[int, SHA1]] = frozenset(),
        process_all: bool = False,
    ) -> Iterable[DetectFileLanguages]:
        file_versions: List[FileVersion] = []

        conflicts = group.as_changeset.conflicts
        decode_old = group.as_changeset.decode_old
        decode_new = group.as_changeset.decode_new

        for changed_file in changed_files:
            logger.debug(f"{changed_file=}")
            if process_all or identify_language_from_path(changed_file.path) is None:
                if (
                    not changed_file.is_added
                    and syntax_highlight_old(changed_file)
                    and (
                        (changed_file.file_id, changed_file.old_sha1)
                        not in skip_file_versions
                    )
                ):
                    assert changed_file.old_sha1
                    file_versions.append(
                        FileVersion(
                            changed_file, changed_file.old_sha1, conflicts, decode_old
                        )
                    )
                if (
                    not changed_file.is_removed
                    and syntax_highlight_new(changed_file)
                    and (
                        (changed_file.file_id, changed_file.new_sha1)
                        not in skip_file_versions
                    )
                ):
                    assert changed_file.new_sha1
                    file_versions.append(
                        FileVersion(
                            changed_file, changed_file.new_sha1, False, decode_new
                        )
                    )

        CHUNK_SIZE = 100

        for offset in range(0, len(file_versions), CHUNK_SIZE):
            yield (
                DetectFileLanguages(group, file_versions[offset : offset + CHUNK_SIZE])
            )
