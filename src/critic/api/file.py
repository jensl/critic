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
from abc import abstractmethod

from typing import Awaitable, Callable, Iterable, Optional, Sequence, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="file"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid file id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised when multiple invalid file ids are used."""

    pass


class InvalidPath(Error):
    """Raised when an invalid (malformed) path is used."""

    def __init__(self, path: str, error: str) -> None:
        """Constructor"""
        super().__init__("Invalid path: %s (%s)" % (path, error))


class MissingPaths(Error):
    """Raised when valid but unrecorded paths are used.

    Typically, this means |create_if_missing=True| should have been used."""

    def __init__(self, paths: Iterable[str]) -> None:
        """Constructor"""
        super().__init__("Missing paths: %s" % ", ".join(sorted(paths)))


class File(api.APIObjectWithId):
    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return "%s(id=%d, path=%r)" % (type(self).__name__, self.id, self.path)

    @property
    @abstractmethod
    def id(self) -> int:
        """The path's unique id"""
        ...

    @property
    @abstractmethod
    def path(self) -> str:
        """The path"""
        ...


@overload
async def fetch(critic: api.critic.Critic, file_id: int, /) -> File:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, path: str, create_if_missing: bool = False
) -> File:
    ...


async def fetch(
    critic: api.critic.Critic,
    file_id: Optional[int] = None,
    /,
    *,
    path: Optional[str] = None,
    create_if_missing: bool = False,
) -> File:
    """Fetch a "file" (file id / path mapping)

    If a path is used, and |create| is True, a mapping is created if one didn't
    already exist."""
    return await fetchImpl.get()(critic, file_id, path, create_if_missing)


@overload
async def fetchMany(
    critic: api.critic.Critic, file_ids: Iterable[int], /
) -> Sequence[File]:
    ...


@overload
async def fetchMany(
    critic: api.critic.Critic,
    /,
    *,
    paths: Iterable[str],
    create_if_missing: bool = False,
) -> Sequence[File]:
    ...


async def fetchMany(
    critic: api.critic.Critic,
    file_ids: Optional[Iterable[int]] = None,
    *,
    paths: Optional[Iterable[str]] = None,
    create_if_missing: bool = False,
) -> Sequence[File]:
    """Fetch multiple "files" (file id / path mappings)

    If paths are used, and |create| is True, a mapping is created if one didn't
    already exist."""
    return await fetchManyImpl.get()(critic, file_ids, paths, bool(create_if_missing))


resource_name = table_name = "files"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[str],
            bool,
        ],
        Awaitable[File],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[Iterable[int]],
            Optional[Iterable[str]],
            bool,
        ],
        Awaitable[Sequence[File]],
    ]
] = FunctionRef()
