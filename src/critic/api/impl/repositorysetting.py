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

from typing import Callable, Tuple, Optional, Sequence, Any

from critic import api
from critic.api import repositorysetting as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.RepositorySetting
ArgumentsType = Tuple[int, int, str, str, Any]


class RepositorySetting(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__repository_id,
            self.__scope,
            self.__name,
            self.__value,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    def scope(self) -> str:
        return self.__scope

    @property
    def name(self) -> str:
        return self.__name

    @property
    def value(self) -> Any:
        return self.__value

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "repository", "scope", "name", "value"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    repository: Optional[api.repository.Repository],
    scope: Optional[str],
    name: Optional[str],
) -> PublicType:
    if setting_id is not None:
        setting = await RepositorySetting.ensureOne(
            setting_id, queries.idFetcher(critic, RepositorySetting)
        )
        return setting

    assert repository and scope and name
    return RepositorySetting.storeOne(
        await queries.query(
            critic, repository=repository, scope=scope, name=name
        ).makeOne(RepositorySetting, public.NotDefined(scope, name))
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    scope: Optional[str],
) -> Sequence[PublicType]:
    return RepositorySetting.store(
        await queries.query(critic, repository=repository, scope=scope).make(
            RepositorySetting
        )
    )
