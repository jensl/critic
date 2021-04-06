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
from dataclasses import dataclass
from typing import Collection, Sequence, Union, Optional, Tuple


logger = logging.getLogger(__name__)

from critic import api
from critic.api import filecontent as public
from critic.api.apiobject import Actual
from critic import diff
from critic.gitaccess import SHA1
from critic.syntaxhighlight import requestHighlight, language
from critic.syntaxhighlight.ranges import SyntaxHighlightRanges
from .apiobject import APIObjectImpl
from .filediff.parthelper import PartHelper


@dataclass(frozen=True)
class Line:
    __offset: int
    __content: Sequence[api.filediff.Part]

    @property
    def offset(self) -> int:
        return self.__offset

    @property
    def content(self) -> Sequence[api.filediff.Part]:
        return self.__content


PublicType = public.FileContent
ArgumentsType = Tuple[api.repository.Repository, SHA1, Optional[api.file.File]]


class FileContent(PublicType, APIObjectImpl, module=public):
    wrapper_class = api.filecontent.FileContent

    __plain_lines: Optional[Sequence[str]]

    def __init__(
        self,
        repository: api.repository.Repository,
        sha1: SHA1,
        commit: Optional[api.commit.Commit],
        file: Optional[api.file.File],
    ):
        self.__repository = repository
        self.__sha1 = sha1
        self.__commit = commit
        self.__file = file
        self.__plain_lines = None

    def __hash__(self) -> int:
        return hash((self.__repository, self.__sha1, self.__file))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileContent)
            and self.repository == other.repository
            and self.sha1 == other.sha1
            and self.file == other.file
        )

    def getCacheKeys(self) -> Collection[object]:
        return ((self.__repository, self.__sha1, self.__file),)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def repository(self) -> api.repository.Repository:
        return self.__repository

    @property
    def file(self) -> Optional[api.file.File]:
        return self.__file

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    async def getLines(  # type: ignore[override]
        self,
        first_line: Optional[int] = None,
        last_line: Optional[int] = None,
        *,
        plain: bool = False,
        syntax: Optional[str] = None,
    ) -> Union[Sequence[str], Sequence[Line]]:
        if first_line is None:
            first_line = 0
        else:
            first_line -= 1

        if plain:
            if self.__plain_lines is None:
                blob = (
                    await self.repository.low_level.fetchone(
                        self.sha1, wanted_object_type="blob"
                    )
                ).asBlob()
                decoder = await self.repository.getFileContentDecoder(
                    self.__commit, self.__file
                )
                self.__plain_lines = diff.parse.splitlines(decoder(blob.data))
            return self.__plain_lines[first_line:last_line]

        if syntax is None and self.file is not None:
            language.setup()
            syntax = language.identify_language_from_path(self.file.path)

        async with SyntaxHighlightRanges.make(self.repository) as ranges:
            ranges.add_file_version(self.sha1, syntax, False).add_line_range(
                first_line, last_line
            )
            await ranges.fetch()

        file_version = ranges.file_versions[0]

        if syntax and not file_version.is_highlighted:
            if await requestHighlight(self.repository, self.file, self.sha1, syntax):
                raise api.filecontent.FileContentDelayed()

        lines = file_version.line_ranges[0].lines
        assert lines is not None

        return [
            Line(1 + first_line + index, list(PartHelper.make(content)))
            for index, content in enumerate(lines)
        ]


@public.fetchImpl
async def fetch(
    repository: api.repository.Repository,
    sha1: Optional[SHA1],
    commit: Optional[api.commit.Commit],
    file: Optional[api.file.File],
) -> PublicType:
    if commit:
        assert file
        try:
            file_information = await commit.getFileInformation(file)
        except api.commit.NotAFile:
            file_information = None
        if not file_information:
            raise api.filecontent.NoSuchFile(file.path)
        sha1 = file_information.sha1
    assert sha1
    return FileContent.storeOne(FileContent(repository, sha1, commit, file))
