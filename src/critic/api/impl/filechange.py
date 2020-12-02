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

from typing import Tuple, Optional, Any, Sequence, List, Iterable

from critic import api
from critic.api import filechange as public
from critic.gitaccess import SHA1
from . import apiobject


WrapperType = api.filechange.FileChange
ArgumentsType = Tuple[
    api.changeset.Changeset,
    api.file.File,
    Optional[SHA1],
    Optional[int],
    Optional[SHA1],
    Optional[int],
]
CacheKeyType = Tuple[int, int]


class FileChange(apiobject.APIObject[WrapperType, ArgumentsType, CacheKeyType]):
    wrapper_class = api.filechange.FileChange

    def __init__(self, args: ArgumentsType):
        (
            self.changeset,
            self.file,
            old_sha1,
            self.old_mode,
            new_sha1,
            self.new_mode,
        ) = args

        self.old_sha1 = old_sha1 if old_sha1 != "0" * 40 else None
        self.new_sha1 = new_sha1 if new_sha1 != "0" * 40 else None

    @staticmethod
    def cacheKey(wrapper: WrapperType) -> CacheKeyType:
        return (wrapper.changeset.id, wrapper.file.id)

    @classmethod
    def makeCacheKey(cls, args: ArgumentsType) -> CacheKeyType:
        changeset, file, *_ = args
        return (changeset.id, file.id)

    @staticmethod
    def fetchCacheKey(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[api.critic.Critic, Optional[CacheKeyType]]:
        changeset: api.changeset.Changeset = args[0]
        file: api.file.File = args[1]
        return critic, (changeset.id, file.id)

    @staticmethod
    def fetchManyCacheKeys(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[
        api.critic.Critic, Optional[List[CacheKeyType]], Optional[Iterable[Any]]
    ]:
        changeset: api.changeset.Changeset = args[0]
        files: Sequence[api.file.File] = args[1]
        return (changeset.critic, [(changeset.id, file.id) for file in files], files)


@public.fetchImpl
@FileChange.cached
async def fetch(
    critic: api.critic.Critic, changeset: api.changeset.Changeset, file: api.file.File
) -> WrapperType:
    critic = changeset.critic
    async with critic.query(
        """SELECT old_sha1, old_mode, new_sha1, new_mode
             FROM changesetfiles
            WHERE changeset={changeset}
              AND file={file}""",
        changeset=changeset,
        file=file,
    ) as result:
        return await FileChange.makeOne(critic, (changeset, file) + await result.one())


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    changeset: api.changeset.Changeset,
    files: Sequence[api.file.File],
) -> Sequence[WrapperType]:
    async with api.critic.Query[
        Tuple[int, Optional[SHA1], Optional[int], Optional[SHA1], Optional[int]]
    ](
        critic,
        """SELECT file, old_sha1, old_mode, new_sha1, new_mode
             FROM changesetfiles
            WHERE changeset={changeset}
              AND {file=file_ids:array}""",
        changeset=changeset,
        file_ids=[file.id for file in files],
    ) as result:
        rows = {row[0]: row[1:] async for row in result}
    if len(rows) < len(files):
        invalid_files = set(file for file in files if file not in rows)
        raise api.filechange.InvalidIds(
            invalid_ids=[(changeset.id, file.id) for file in invalid_files]
        )
    return await FileChange.make(
        critic, ((changeset, file) + rows[file.id] for file in files)  # type: ignore
    )


@public.fetchAllImpl
async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[WrapperType]:
    critic = changeset.critic

    async with api.critic.Query[int](
        critic,
        """SELECT file
             FROM changesetfiles
            WHERE changeset={changeset}""",
        changeset=changeset,
    ) as result:
        file_ids = await result.scalars()

    files = sorted(
        await api.file.fetchMany(critic, file_ids), key=lambda file: file.path
    )

    return await fetchMany(critic, changeset, files)
