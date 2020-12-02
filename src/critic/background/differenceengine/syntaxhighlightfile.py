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
import stat
from typing import Sequence, Iterable

logger = logging.getLogger(__name__)

from . import protocol
from .requestjob import RequestJob, GroupType
from .changedfile import ChangedFile

from ...syntaxhighlight.language import identify_language_from_path

from critic import api
from critic import dbaccess
from critic import textutils
from critic import pubsub
from critic.dbaccess import Query
from critic.gitaccess import GitBlob, SHA1


def syntax_highlight_old(changed_file: ChangedFile) -> bool:
    old_status, _ = changed_file.required_status
    return (
        isinstance(old_status, int)
        and old_status > 0
        and not stat.S_ISLNK(changed_file.required_old_mode)
    )


def syntax_highlight_new(changed_file: ChangedFile) -> bool:
    _, new_status = changed_file.required_status
    return (
        isinstance(new_status, int)
        and new_status > 0
        and not stat.S_ISLNK(changed_file.required_new_mode)
    )


class SyntaxHighlightFile(RequestJob[protocol.SyntaxHighlighFile.Response]):
    # Syntax highlight files after after calculating file differences in all
    # files.
    priority = 2  # CalculateFileDifference.priority + 1

    result_type = list

    # Failure to syntax highlight a file is non-fatal; we can just display a
    # non-highlighted version of the file.
    is_fatal = False

    def __init__(
        self,
        group: GroupType,
        sha1: SHA1,
        language_label: str,
        conflicts: bool,
    ):
        super().__init__(group, (sha1, language_label, conflicts))
        self.sha1 = sha1
        self.language_label = language_label
        self.conflicts = conflicts
        self.language_id = group.language_ids.get_id(self.language_label)

    async def issue_requests(
        self, client: pubsub.Client
    ) -> Sequence[pubsub.OutgoingRequest]:
        async with self.group.repository() as repository:
            source = textutils.decode(
                (
                    await repository.fetchone(
                        self.sha1, object_factory=GitBlob, wanted_object_type="blob"
                    )
                ).data
            )

        pubsub_client = await self.service.pubsub_client

        return [
            await pubsub_client.request(
                pubsub.Payload(
                    protocol.SyntaxHighlighFile.Request(source, self.language_label)
                ),
                pubsub.ChannelName("syntaxhighlightfile"),
            )
        ]

    async def update_database(self, critic: api.critic.Critic) -> None:
        if not self.responses:
            return
        [response] = self.responses
        lines = response.lines
        contexts = response.contexts
        async with critic.transaction() as cursor:
            await cursor.execute(
                """INSERT
                     INTO highlightfiles (
                            repository, sha1, language, conflicts
                          ) VALUES (
                            {repository_id}, {sha1}, {language_id}, {conflicts}
                          ) ON CONFLICT DO NOTHING""",
                repository_id=self.group.repository_id,
                sha1=self.sha1,
                language_id=self.language_id,
                conflicts=self.conflicts,
            )
            async with Query[int](
                cursor,
                """SELECT id
                     FROM highlightfiles
                    WHERE repository={repository_id}
                      AND sha1={sha1}
                      AND language={language_id}
                      AND conflicts={conflicts}""",
                repository_id=self.group.repository_id,
                sha1=self.sha1,
                language_id=self.language_id,
                conflicts=self.conflicts,
            ) as result:
                file_id = await result.scalar()
            await cursor.execute(
                """UPDATE highlightfiles
                      SET highlighted=TRUE,
                          requested=FALSE
                    WHERE id={file_id}""",
                file_id=file_id,
            )
            await cursor.execute(
                """DELETE
                     FROM highlightlines
                    WHERE file={file_id}""",
                file_id=file_id,
            )
            await cursor.executemany(
                """INSERT
                     INTO highlightlines (
                            file, line, data
                          ) VALUES (
                            {file_id}, {index}, {data}
                          )""",
                [
                    dict(file_id=file_id, index=index, data=data)
                    for index, data in enumerate(lines)
                ],
            )
            await cursor.execute(
                """DELETE
                     FROM codecontexts
                    WHERE sha1={sha1}
                      AND language={language_id}""",
                sha1=self.sha1,
                language_id=self.language_id,
            )
            await cursor.executemany(
                """INSERT INTO codecontexts (
                     sha1, language, first_line, last_line, context
                   ) VALUES (
                     {sha1}, {language_id}, {first_line}, {last_line}, {context}
                   )""",
                (
                    dbaccess.parameters(
                        sha1=self.sha1,
                        language_id=self.language_id,
                        first_line=first_line,
                        last_line=last_line,
                        context=context,
                    )
                    for first_line, last_line, context in contexts
                ),
            )

    @staticmethod
    def for_files(
        group: GroupType, changed_files: Sequence[ChangedFile]
    ) -> Iterable[SyntaxHighlightFile]:
        """Return a set of SyntaxHighlightFile jobs

        The returned tuples indicate file versions that may need to be syntax
        highlighted, and for which the appropriate language could be deduced
        from the file's path alone."""

        conflicts = group.conflicts

        for changed_file in changed_files:
            language_label = identify_language_from_path(changed_file.path)
            if language_label is not None:
                if syntax_highlight_old(changed_file):
                    yield SyntaxHighlightFile(
                        group, changed_file.required_old_sha1, language_label, conflicts
                    )

                if syntax_highlight_new(changed_file):
                    yield SyntaxHighlightFile(
                        group, changed_file.required_new_sha1, language_label, False
                    )
