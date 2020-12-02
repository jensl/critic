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

from typing import (
    Awaitable,
    Callable,
    Optional,
    Sequence,
    Literal,
    Union,
    Protocol,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef
from critic.gitaccess import SHA1


class Error(api.APIError, object_type="file content"):
    pass


class NoSuchFile(Error):
    pass


class FileContentDelayed(api.ResultDelayedError):
    pass


class FileContent(api.APIObject):
    """Representation of the contents of a file"""

    def __hash__(self) -> int:
        return hash((self.repository.id, self.file, self.sha1))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileContent)
            and self.repository == other.repository
            and self.file == other.file
            and self.sha1 == other.sha1
        )

    @property
    def repository(self) -> api.repository.Repository:
        return self._impl.repository

    @property
    def file(self) -> api.file.File:
        return self._impl.file

    @property
    def sha1(self) -> SHA1:
        return self._impl.sha1

    @overload
    async def getLines(
        self,
        first_line: Optional[int] = None,
        last_line: Optional[int] = None,
        *,
        plain: Literal[True],
    ) -> Sequence[str]:
        ...

    @overload
    async def getLines(
        self,
        first_line: Optional[int] = None,
        last_line: Optional[int] = None,
        *,
        syntax: Optional[str] = None,
    ) -> Sequence[Line]:
        ...

    async def getLines(
        self,
        first_line: Optional[int] = None,
        last_line: Optional[int] = None,
        *,
        plain: bool = False,
        syntax: Optional[str] = None,
    ) -> Union[Sequence[str], Sequence[Line]]:
        if first_line is not None:
            first_line = int(first_line)
            assert first_line > 0
        if last_line is not None:
            last_line = int(last_line)
            assert last_line > 0
        assert not first_line or not last_line or first_line <= last_line
        assert not plain or syntax is None

        return await self._impl.getLines(
            self.critic, first_line, last_line, plain, syntax
        )


class Line(Protocol):
    """Representation of a syntax highlighted line from some version of a file"""

    @property
    def content(self) -> Sequence[api.filediff.Part]:
        ...

    @property
    def offset(self) -> int:
        ...


@overload
async def fetch(
    repository: api.repository.Repository,
    /,
    *,
    sha1: SHA1,
    file: Optional[api.file.File] = None,
) -> FileContent:
    ...


@overload
async def fetch(
    repository: api.repository.Repository,
    /,
    *,
    commit: api.commit.Commit,
    file: api.file.File,
) -> FileContent:
    ...


async def fetch(
    repository: api.repository.Repository,
    /,
    *,
    sha1: Optional[SHA1] = None,
    commit: Optional[api.commit.Commit] = None,
    file: Optional[api.file.File] = None,
) -> FileContent:
    """Retrieve the contents of a file

    If |sha1| is not None, it should be the full 40 character hexadecimal
    SHA-1 sum of the file's blob. No checking will be made to ensure it is
    actually referenced by any particular path in any particular commit. If
    |file| is also used, it only helps in determining the file's syntax. Can
    not be combined with |commit|.

    If |commit| is not None, |file| must also be used, and the contents of
    the file in the specified commit are retrieved."""
    return await fetchImpl.get()(repository, sha1, commit, file)


resource_name = "filecontents"


fetchImpl: FunctionRef[
    Callable[
        [
            api.repository.Repository,
            Optional[SHA1],
            Optional[api.commit.Commit],
            Optional[api.file.File],
        ],
        Awaitable[FileContent],
    ]
] = FunctionRef()
