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
from typing import Collection, Mapping, Tuple, Optional, Sequence

from critic import api
from critic.api import filechange as public
from critic.api.apiobject import Actual
from critic.gitaccess import SHA1
from .apiobject import APIObjectImpl
from .file import create as createFiles
from .queryhelper import QueryHelper


PublicType = public.FileChange
CacheKeyType = Tuple[int, int]


class FileChange(PublicType, APIObjectImpl, module=public):
    wrapper_class = api.filechange.FileChange

    def __init__(
        self,
        changeset: api.changeset.Changeset,
        file: api.file.File,
        old_sha1: Optional[SHA1],
        old_mode: Optional[int],
        new_sha1: Optional[SHA1],
        new_mode: Optional[int],
    ):
        super().__init__(changeset.critic)
        self.__changeset = changeset
        self.__file = file
        self.__old_sha1 = old_sha1 if old_sha1 != "0" * 40 else None
        self.__old_mode = old_mode
        self.__new_sha1 = new_sha1 if new_sha1 != "0" * 40 else None
        self.__new_mode = new_mode

    def __hash__(self) -> int:
        return hash((self.__changeset, self.__file))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileChange)
            and self.__changeset == other.__changeset
            and self.__file == other.__file
        )

    def __lt__(self, other: object) -> bool:
        return isinstance(other, FileChange) and (
            self.__changeset < other.__changeset
            or (self.changeset == other.changeset and self.file < other.file)
        )

    def getCacheKeys(self) -> Collection[object]:
        return ((self.__changeset, self.__file),)

    @property
    def changeset(self) -> api.changeset.Changeset:
        return self.__changeset

    @property
    def file(self) -> api.file.File:
        return self.__file

    @property
    def old_sha1(self) -> Optional[SHA1]:
        return self.__old_sha1

    @property
    def old_mode(self) -> Optional[int]:
        return self.__old_mode

    @property
    def new_sha1(self) -> Optional[SHA1]:
        return self.__new_sha1

    @property
    def new_mode(self) -> Optional[int]:
        return self.__new_mode

    async def refresh(self: Actual) -> Actual:
        return self


RowType = Tuple[int, int, Optional[SHA1], Optional[int], Optional[SHA1], Optional[int]]

queries = QueryHelper[RowType](
    FileChange.getTableName(),
    "changeset",
    "file",
    "old_sha1",
    "old_mode",
    "new_sha1",
    "new_mode",
)


@dataclass
class MakeOne:
    changeset: api.changeset.Changeset
    file: api.file.File

    def __call__(self, critic: api.critic.Critic, args: RowType) -> FileChange:
        changeset_id, file_id, old_sha1, old_mode, new_sha1, new_mode = args
        assert changeset_id == self.changeset.id
        assert file_id == self.file.id
        return FileChange(
            self.changeset, self.file, old_sha1, old_mode, new_sha1, new_mode
        )


@dataclass
class MakeMultiple:
    changeset: api.changeset.Changeset
    files: Mapping[int, api.file.File]

    def __call__(self, critic: api.critic.Critic, args: RowType) -> FileChange:
        changeset_id, file_id, old_sha1, old_mode, new_sha1, new_mode = args
        assert changeset_id == self.changeset.id
        assert file_id in self.files
        file = self.files[file_id]
        return FileChange(self.changeset, file, old_sha1, old_mode, new_sha1, new_mode)


@dataclass
class FetchOne:
    critic: api.critic.Critic

    async def __call__(
        self, args: Tuple[api.changeset.Changeset, api.file.File]
    ) -> FileChange:
        changeset, file = args
        return await queries.query(self.critic, changeset=changeset, file=file).makeOne(
            MakeOne(changeset, file)
        )


@dataclass
class FetchMultiple:
    critic: api.critic.Critic

    async def __call__(
        self, args: Sequence[Tuple[api.changeset.Changeset, api.file.File]]
    ) -> Sequence[FileChange]:
        changeset = args[0][0]
        files = [file for _, file in args]
        return await queries.query(self.critic, changeset=changeset, file=files).make(
            MakeMultiple(changeset, {file.id: file for file in files})
        )


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, changeset: api.changeset.Changeset, file: api.file.File
) -> PublicType:
    return await FileChange.ensureOne((changeset, file), FetchOne(critic))


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    changeset: api.changeset.Changeset,
    files: Sequence[api.file.File],
) -> Sequence[PublicType]:
    return await FileChange.ensure(
        [(changeset, file) for file in files], FetchMultiple(critic)
    )


@public.fetchAllImpl
async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[PublicType]:
    critic = changeset.critic

    async with api.critic.Query[Tuple[int, str]](
        critic,
        """SELECT id, path
             FROM files
             JOIN changesetfiles ON (file=id)
            WHERE changeset={changeset}""",
        changeset=changeset,
    ) as result:
        files = await result.all()

    sorted_files = sorted(createFiles(critic, files), key=lambda file: file.path)

    return await fetchMany(critic, changeset, sorted_files)
