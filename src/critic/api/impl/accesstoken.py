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

from typing import Tuple, Optional, Set, Sequence, Mapping, Any, Type, List

from critic import api
from critic.api import accesstoken as public
from . import apiobject
from .accesscontrolprofile import AccessControlProfile


WrapperType = api.accesstoken.AccessToken
ArgumentsType = Tuple[
    int, api.accesstoken.AccessType, int, str, Optional[str], Optional[int]
]


class AccessToken(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.accesstoken.AccessToken
    column_names = [
        "id",
        "access_type",
        "uid",
        "token",
        "title",
        "accesscontrolprofiles.id",
    ]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.access_type,
            self.__user_id,
            self.token,
            self.title,
            self.__profile_id,
        ) = args

    async def getUser(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.__user_id is None:
            return None
        return await api.user.fetch(critic, self.__user_id)

    async def getProfile(
        self, critic: api.critic.Critic
    ) -> Optional[api.accesscontrolprofile.AccessControlProfile]:
        if self.__profile_id is None:
            return None
        return await api.accesscontrolprofile.fetch(critic, self.__profile_id)

    @classmethod
    def default_joins(cls) -> Sequence[str]:
        acps = AccessControlProfile.table()
        return [f"{acps} ON ({acps}.access_token={AccessToken.table()}.id)"]

    @classmethod
    async def refresh(
        cls: Type[AccessToken],
        critic: api.critic.Critic,
        tables: Set[str],
        cached_objects: Mapping[Any, WrapperType],
    ) -> None:
        if not tables.intersection(("accesstokens", "accesscontrolprofiles")):
            return
        await super().refresh(critic, tables, cached_objects)


@public.fetchImpl
@AccessToken.cached
async def fetch(critic: api.critic.Critic, token_id: int) -> WrapperType:
    async with AccessToken.query(
        critic, ["accesstokens.id={token_id}"], token_id=token_id
    ) as result:
        return await AccessToken.makeOne(critic, result)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, user: Optional[api.user.User]
) -> List[WrapperType]:
    conditions = []
    if user is not None:
        conditions.append("uid={user}")
    async with AccessToken.query(critic, conditions, user=user) as result:
        return await AccessToken.make(critic, result)
