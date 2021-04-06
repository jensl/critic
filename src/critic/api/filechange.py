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

from typing import Awaitable, Callable, Iterable, Sequence, Optional

from critic import api
from critic.api.apiobject import FunctionRef
from critic.gitaccess import SHA1


class Error(api.APIError, object_type="file change"):
    pass


class InvalidId(api.InvalidIdError, Error):
    pass


class InvalidIds(api.InvalidIdsError, Error):
    pass


class FileChange(api.APIObject):
    """Representation of the changes to a file introduced by a changeset"""

    @abstractmethod
    def __lt__(self, other: object) -> bool:
        ...

    @property
    @abstractmethod
    def changeset(self) -> api.changeset.Changeset:
        ...

    @property
    @abstractmethod
    def file(self) -> api.file.File:
        ...

    @property
    @abstractmethod
    def old_sha1(self) -> Optional[SHA1]:
        ...

    @property
    @abstractmethod
    def old_mode(self) -> Optional[int]:
        ...

    @property
    @abstractmethod
    def new_sha1(self) -> Optional[SHA1]:
        ...

    @property
    @abstractmethod
    def new_mode(self) -> Optional[int]:
        ...

    @property
    def was_added(self) -> bool:
        return self.old_sha1 is None

    @property
    def was_deleted(self) -> bool:
        return self.new_sha1 is None


async def fetch(changeset: api.changeset.Changeset, file: api.file.File) -> FileChange:
    return await fetchImpl.get()(changeset.critic, changeset, file)


async def fetchMany(
    changeset: api.changeset.Changeset, files: Iterable[api.file.File]
) -> Sequence[FileChange]:
    return await fetchManyImpl.get()(changeset.critic, changeset, list(files))


async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[FileChange]:
    return await fetchAllImpl.get()(changeset)


resource_name = "filechanges"
table_name = "changesetfiles"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, api.changeset.Changeset, api.file.File],
        Awaitable[FileChange],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [api.critic.Critic, api.changeset.Changeset, Sequence[api.file.File]],
        Awaitable[Sequence[FileChange]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[[api.changeset.Changeset], Awaitable[Sequence[FileChange]]]
] = FunctionRef()
