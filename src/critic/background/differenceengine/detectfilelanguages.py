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
    TypedDict,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.dbaccess import Parameters
from critic.gitaccess import SHA1

from .changeset import Changeset
from .changedfile import ChangedFile
from .job import Job
from .examinefiles import ExamineFiles
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


class DetectFileLanguages(Job[Changeset]):
    # Detect file languages quite soon.
    priority = ExamineFiles.priority + 1

    # Failure to syntax highlight a file is non-fatal; we can just display a
    # non-highlighted version of the file.
    is_fatal = False

    result_type = (type(None), str)

    language_by_sha1: Dict[SHA1, Language]

    def __init__(
        self, group: Changeset, file_versions: Sequence[Tuple[ChangedFile, SHA1, bool]]
    ):
        super().__init__(
            group,
            tuple(
                changed_file.required_file_id for changed_file, _, _ in file_versions
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

        from_source_sha1s = set()

        for (changed_file, sha1, _) in self.file_versions:
            label = identify_language_from_path(changed_file.path)
            if label is not None:
                language_id = self.group.language_ids.get_id(label)
                if language_id is not None:
                    self.language_by_sha1[sha1] = Language(label, language_id)
            else:
                from_source_sha1s.add(sha1)

        if from_source_sha1s:
            async with self.group.repository() as repository:
                for sha1 in from_source_sha1s:
                    label = await identify_language_from_source(repository, sha1)
                    if label is not None:
                        language_id = self.group.language_ids.get_id(label)
                        if language_id is not None:
                            self.language_by_sha1[sha1] = Language(label, language_id)

    async def update_database(self, critic: api.critic.Critic) -> None:
        changeset_id = self.group.changeset_id
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
                    dict(
                        repository_id=repository_id,
                        sha1=sha1,
                        language_id=self.language_by_sha1[sha1].id,
                        conflicts=conflicts,
                    )
                    for changed_file, sha1, conflicts in self.file_versions
                    if sha1 in self.language_by_sha1
                ),
            )

            old_highlightfile_updates: List[Parameters] = []
            new_highlightfile_updates: List[Parameters] = []

            for changed_file, sha1, conflicts in self.file_versions:
                if sha1 not in self.language_by_sha1:
                    continue
                if sha1 == changed_file.old_sha1:
                    updates = old_highlightfile_updates
                else:
                    updates = new_highlightfile_updates
                updates.append(
                    dict(
                        changeset_id=changeset_id,
                        file_id=changed_file.file_id,
                        repository_id=repository_id,
                        sha1=sha1,
                        language_id=self.language_by_sha1[sha1].id,
                        conflicts=conflicts,
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

    def follow_ups(self) -> Iterable[SyntaxHighlightFile]:
        for changed_file, sha1, conflicts in self.file_versions:
            language = self.language_by_sha1.get(sha1)
            if language is None:
                continue
            yield SyntaxHighlightFile(self.group, sha1, language.label, conflicts)

    @staticmethod
    def for_files(
        changeset: Changeset,
        changed_files: Iterable[ChangedFile],
        *,
        skip_file_versions: Collection[Tuple[int, SHA1]] = frozenset(),
        process_all: bool = False,
    ) -> Iterable[DetectFileLanguages]:
        file_versions: List[Tuple[ChangedFile, SHA1, bool]] = []

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
                        (changed_file, changed_file.old_sha1, changeset.conflicts)
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
                    file_versions.append((changed_file, changed_file.new_sha1, False))

        CHUNK_SIZE = 100

        for offset in range(0, len(file_versions), CHUNK_SIZE):
            yield (
                DetectFileLanguages(
                    changeset, file_versions[offset : offset + CHUNK_SIZE]
                )
            )
