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

from typing import Callable, Tuple, Any, Optional, Sequence

from critic import api
from critic.api import usersetting as public
from .queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId


PublicType = public.UserSetting
ArgumentsType = Tuple[int, int, str, str, Any]


class UserSetting(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__user_id, self.__scope, self.__name, self.__value) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def user(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__user_id)

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
    PublicType.getTableName(), "id", "uid", "scope", "name", "value"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    scope: Optional[str],
    name: Optional[str],
) -> PublicType:
    if setting_id is not None:
        setting = await UserSetting.ensureOne(
            setting_id, queries.idFetcher(critic, UserSetting)
        )
        api.PermissionDenied.raiseUnlessUser(critic, await setting.user)
        return setting

    assert scope and name
    return UserSetting.storeOne(
        await queries.query(
            critic, uid=critic.effective_user, scope=scope, name=name
        ).makeOne(UserSetting, public.NotDefined(scope, name))
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, scope: Optional[str]
) -> Sequence[PublicType]:
    return UserSetting.store(
        await queries.query(critic, uid=critic.effective_user, scope=scope).make(
            UserSetting
        )
    )
