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

import hashlib
import logging
from typing import Collection, Iterable, Dict, Tuple, Sequence, List, Optional

from .queryhelper import QueryHelper

logger = logging.getLogger(__name__)

from critic import api
from critic.api import file as public
from critic import base
from critic import dbaccess
from .apiobject import APIObjectImplWithId


PublicType = public.File
ArgumentsType = Tuple[int, str]


class File(PublicType, APIObjectImplWithId, module=public):
    wrapper_class = public.File

    def update(self, args: ArgumentsType) -> int:
        self.__id, self.__path = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def path(self) -> str:
        return self.__path

    @classmethod
    async def doRefreshAll(
        cls, critic: api.critic.Critic, files: Collection[object], /
    ) -> None:
        pass


def _check_path(path: str) -> None:
    if path.startswith("/"):
        raise public.InvalidPath(path, "leading path separator")
    if path.endswith("/"):
        raise public.InvalidPath(path, "trailing path separator")


async def _translate_paths(
    critic: api.critic.Critic, paths: Iterable[str]
) -> Dict[str, int]:
    paths = set(paths)
    md5_hashes = [hashlib.md5(path.encode()).hexdigest() for path in paths]

    async with api.critic.Query[Tuple[str, int]](
        critic,
        """SELECT path, id
             FROM files
            WHERE MD5(path)=ANY({md5_hashes})""",
        md5_hashes=md5_hashes,
    ) as result:
        translated = dict(await result.all())

    # Check that we didn't find any unexpected paths.
    if set(translated) - paths:
        raise base.ImplementationError("MD5 collision in files table!")

    return translated


async def _ensure_paths(
    critic: api.critic.Critic, paths: Iterable[str]
) -> Dict[str, int]:
    paths_set = set(paths)

    translated_paths = await _translate_paths(critic, paths_set)
    missing_paths = paths_set.difference(translated_paths)

    if not missing_paths:
        return translated_paths

    for path in missing_paths:
        _check_path(path)

    while missing_paths:
        try:
            async with critic.database.transaction() as cursor:
                await cursor.executemany(
                    "INSERT INTO files (path) VALUES ({path})",
                    ({"path": path} for path in missing_paths),
                )
        except dbaccess.IntegrityError:
            logger.debug("IntegrityError while inserting paths!")
        translated_paths.update(await _translate_paths(critic, missing_paths))
        missing_paths.difference_update(translated_paths)

    return translated_paths


async def _resolve_paths(
    critic: api.critic.Critic, paths: Sequence[str], create_if_missing: bool
) -> List[ArgumentsType]:
    if create_if_missing:
        translated_paths = await _ensure_paths(critic, paths)
    else:
        paths_set = set(paths)
        translated_paths = await _translate_paths(critic, paths_set)
        missing_paths = paths_set.difference(translated_paths)
        if missing_paths:
            raise public.MissingPaths(missing_paths)
    return [(translated_paths[path], path) for path in paths]


queries = QueryHelper[ArgumentsType](PublicType.getTableName(), "id", "path")


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    file_id: Optional[int],
    path: Optional[str],
    create_if_missing: bool,
) -> PublicType:
    if file_id is not None:
        return await File.ensureOne(file_id, queries.idFetcher(critic, File))
    assert path is not None
    file_id, _ = (await _resolve_paths(critic, [path], create_if_missing))[0]
    return File.storeOne(File(critic, (file_id, path)))


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    file_ids: Optional[Iterable[int]],
    paths: Optional[Iterable[str]] = None,
    create_if_missing: bool = False,
) -> Sequence[PublicType]:
    if file_ids is not None:
        return await File.ensure([*file_ids], queries.idsFetcher(critic, File))
    assert paths is not None
    return File.store(
        create(critic, await _resolve_paths(critic, [*paths], create_if_missing))
    )


def create(
    critic: api.critic.Critic, files: Sequence[Tuple[int, str]]
) -> Sequence[File]:
    return [File(critic, (file_id, path)) for file_id, path in files]
