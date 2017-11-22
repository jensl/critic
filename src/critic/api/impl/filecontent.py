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
from typing import Sequence, Union, Optional, Tuple, Any

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api
from critic import diff
from critic import textutils
from critic.gitaccess import SHA1
from critic.syntaxhighlight import requestHighlight, language
from critic.syntaxhighlight.ranges import SyntaxHighlightRanges


@dataclass(frozen=True)
class Line:
    offset: int
    content: Sequence[api.filediff.Part]


WrapperType = api.filecontent.FileContent
ArgumentsType = Tuple[api.repository.Repository, SHA1, Optional[api.file.File]]


class FileContent(apiobject.APIObject[WrapperType, ArgumentsType, Any]):
    wrapper_class = api.filecontent.FileContent

    __plain_lines: Optional[Sequence[str]]

    def __init__(self, args: ArgumentsType):
        (self.repository, self.sha1, self.file) = args
        self.__plain_lines = None

    async def getLines(
        self,
        critic: api.critic.Critic,
        first_line: Optional[int],
        last_line: Optional[int],
        plain: bool,
        syntax: Optional[str],
    ) -> Sequence[Union[str, api.filecontent.Line]]:
        from . import filediff

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
                self.__plain_lines = diff.parse.splitlines(textutils.decode(blob.data))
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

        return [
            Line(1 + first_line + index, list(filediff.PartHelper.make(content)))
            for index, content in enumerate(lines)
        ]


async def fetch(
    repository: api.repository.Repository,
    sha1: Optional[SHA1],
    commit: Optional[api.commit.Commit],
    file: Optional[api.file.File],
) -> WrapperType:
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
    return await FileContent.makeOne(repository.critic, (repository, sha1, file))
