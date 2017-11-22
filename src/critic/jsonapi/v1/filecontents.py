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

from typing import Sequence, Optional, TypedDict, Union

from critic import api
from critic import jsonapi
from . import filediffs


Line = TypedDict("Line", {"type": str, "offset": int, "content": filediffs.Parts})


def reduce_line(line: api.filecontent.Line) -> Line:
    return {
        "type": api.filediff.LINE_TYPE_STRINGS[api.filediff.LINE_TYPE_CONTEXT],
        "offset": line.offset,
        "content": filediffs.reduce_parts(line.content),
    }


JSONResult = TypedDict(
    "JSONResult",
    {
        "repository": api.repository.Repository,
        "file": api.file.File,
        "sha1": str,
        "lines": Union[Sequence[str], Sequence[Line]],
    },
)


class FileContents(
    jsonapi.ResourceClass[api.filecontent.FileContent], api_module=api.filecontent
):
    """Context lines for a file in a commit"""

    contexts = (None, "repositories")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.filecontent.FileContent
    ) -> JSONResult:
        """TODO: add documentation"""

        first = parameters.getQueryParameter("first", converter=int)
        last = parameters.getQueryParameter("last", converter=int)

        lines: Union[Sequence[str], Sequence[Line]]
        if parameters.getQueryParameter("plain") == "yes":
            lines = await value.getLines(first, last, plain=True)
        else:
            lines = list(map(reduce_line, await value.getLines(first, last)))

        return {
            "repository": value.repository,
            "file": value.file,
            "sha1": value.sha1,
            "lines": lines,
        }

    @staticmethod
    async def multiple(parameters: jsonapi.Parameters,) -> api.filecontent.FileContent:
        """TODO: add documentation"""

        commit = await Commits.deduce(parameters)
        if commit is None:
            raise jsonapi.UsageError.missingParameter("commit")

        file = await Files.deduce(parameters)
        if file is None:
            raise jsonapi.UsageError.missingParameter("file")

        return await api.filecontent.fetch(commit.repository, commit=commit, file=file)


from .commits import Commits
from .files import Files
