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

from typing import Optional, Sequence, TypedDict, Union

from critic import api
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from .filediffs import Parts, reduce_parts


Line = TypedDict("Line", {"type": str, "offset": int, "content": Parts})


def reduce_line(line: api.filecontent.Line) -> Line:
    return {
        "type": api.filediff.LINE_TYPE_STRINGS[api.filediff.LINE_TYPE_CONTEXT],
        "offset": line.offset,
        "content": reduce_parts(line.content),
    }


class JSONResult(TypedDict):
    repository: api.repository.Repository
    sha1: str
    file: Optional[api.file.File]
    lines: Union[Sequence[str], Sequence[Line]]


class FileContents(
    ResourceClass[api.filecontent.FileContent], api_module=api.filecontent
):
    """Context lines for a file in a commit"""

    contexts = (None, "repositories")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.filecontent.FileContent
    ) -> JSONResult:
        first = parameters.query.get("first", converter=int)
        last = parameters.query.get("last", converter=int)

        lines: Union[Sequence[str], Sequence[Line]]
        if parameters.query.get("plain") == "yes":
            lines = await value.getLines(first, last, plain=True)
        else:
            lines = [reduce_line(line) for line in await value.getLines(first, last)]

        return JSONResult(
            repository=value.repository,
            sha1=value.sha1,
            file=value.file,
            lines=lines,
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> api.filecontent.FileContent:
        commit = await parameters.deduce(api.commit.Commit)
        if commit is None:
            raise UsageError.missingParameter("commit")

        file = await parameters.deduce(api.file.File)
        if file is None:
            raise UsageError.missingParameter("file")

        return await api.filecontent.fetch(commit.repository, commit=commit, file=file)
