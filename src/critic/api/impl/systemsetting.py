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

from typing import Callable, Collection, Tuple, Any, Sequence, Optional

from critic import api
from critic.api import systemsetting as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.SystemSetting
ArgumentsType = Tuple[int, str, str, Any, bool]


class SystemSetting(PublicType, APIObjectImplWithId, module=public):
    def __str__(self) -> str:
        return self.key

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__key,
            self.__description,
            self.__value,
            self.__is_privileged,
        ) = args
        if self.__is_privileged:
            api.PermissionDenied.raiseUnlessSystem(self.critic)
        return self.__id

    def getCacheKeys(self) -> Collection[object]:
        return (self.__id, self.__key)

    @property
    def id(self) -> int:
        """The setting's unique id"""
        return self.__id

    @property
    def key(self) -> str:
        """The setting's unique key"""
        return self.__key

    @property
    def description(self) -> str:
        """The setting's description"""
        return self.__description

    @property
    def is_privileged(self) -> bool:
        return self.__is_privileged

    @property
    def value(self) -> Any:
        """The setting's value"""
        return self.__value

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "key", "description", "value", "privileged"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, setting_id: Optional[int], key: Optional[str]
) -> PublicType:
    if setting_id is not None:
        return await SystemSetting.ensureOne(
            setting_id, queries.idFetcher(critic, SystemSetting)
        )
    assert key is not None
    return await SystemSetting.ensureOne(
        key, queries.itemFetcher(critic, SystemSetting, "key"), public.InvalidKey
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    setting_ids: Optional[Sequence[int]],
    keys: Optional[Sequence[str]],
) -> Sequence[PublicType]:
    if setting_ids is not None:
        return await SystemSetting.ensure(
            setting_ids, queries.idsFetcher(critic, SystemSetting)
        )
    assert keys is not None
    return await SystemSetting.ensure(
        keys, queries.itemsFetcher(critic, SystemSetting, "key"), public.InvalidKeys
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, prefix: Optional[str]
) -> Sequence[PublicType]:
    conditions = []

    try:
        api.PermissionDenied.raiseUnlessSystem(critic)
    except api.PermissionDenied:
        conditions.append("NOT privileged")

    if prefix is not None:
        if "%" in prefix:
            raise api.systemsetting.InvalidPrefix(prefix)
        conditions.append("key LIKE {prefix}")
        prefix += ".%"

    return SystemSetting.store(
        await queries.query(critic, *conditions, prefix=prefix).make(SystemSetting)
    )
