# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from typing import Callable, Optional, Sequence, Tuple

from critic import api
from critic.api import accesstoken as public
from .queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId


PublicType = public.AccessToken
ArgumentsType = Tuple[int, public.AccessType, int, str, Optional[str], Optional[int]]


class AccessToken(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__access_type,
            self.__user_id,
            self.__token,
            self.__title,
            self.__profile_id,
        ) = args
        return self.__id

    @property
    def access_type(self) -> public.AccessType:
        """The type of access granted by this access token"""
        return self.__access_type

    @property
    def id(self) -> int:
        """The access token's unique id"""
        return self.__id

    @property
    async def user(self) -> Optional[api.user.User]:
        """The user authenticated by the access token, or None"""
        if self.__user_id is None:
            return None
        return await api.user.fetch(self.critic, self.__user_id)

    @property
    def token(self) -> str:
        """The actual secret token"""
        return self.__token

    @property
    def title(self) -> Optional[str]:
        """The access token's title, or None"""
        return self.__title

    @property
    async def profile(self) -> Optional[api.accesscontrolprofile.AccessControlProfile]:
        """The access token's access control profile"""
        if self.__profile_id is None:
            return None
        return await api.accesscontrolprofile.fetch(self.critic, self.__profile_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


_acps = api.accesscontrolprofile.AccessControlProfile.getTableName()
_ats = PublicType.getTableName()

queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "access_type",
    "uid",
    "token",
    "title",
    "accesscontrolprofiles.id",
    default_joins=[f"{_acps} ON ({_acps}.access_token={_ats}.id)"],
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, token_id: int) -> PublicType:
    return await AccessToken.ensureOne(
        token_id, queries.idFetcher(critic, AccessToken), public.InvalidId
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, user: Optional[api.user.User]
) -> Sequence[PublicType]:
    conditions = []
    if user is not None:
        conditions.append("uid={user}")
    return AccessToken.store(
        await queries.query(critic, *conditions, user=user).make(AccessToken)
    )
