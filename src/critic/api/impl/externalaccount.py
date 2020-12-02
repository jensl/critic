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

import logging
from typing import Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api import externalaccount as public
from .apiobject import APIObject


WrapperType = api.externalaccount.ExternalAccount
ArgumentsType = Tuple[
    int, Optional[int], str, str, Optional[str], Optional[str], Optional[str]
]


class ExternalAccount(APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    table_name = "externalusers"
    column_names = ["id", "uid", "provider", "account", "username", "fullname", "email"]

    def __init__(self, args: ArgumentsType):
        from critic import auth

        (
            self.id,
            self.__user_id,
            self.provider_name,
            self.account_id,
            self.account_username,
            self.account_fullname,
            self.account_email,
        ) = args

        provider = auth.Provider.enabled().get(self.provider_name)

        self.enabled = provider is not None
        self.provider_title = provider.getTitle() if provider else None
        self.account_url = provider.getAccountURL(self.account_id) if provider else None

    @property
    def is_connected(self) -> bool:
        return self.__user_id is not None

    def getProvider(self) -> Optional[api.externalaccount.Provider]:
        from critic import auth

        return auth.Provider.enabled().get(self.provider_name)

    async def getUser(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.__user_id is None:
            return None
        return await api.user.fetch(critic, self.__user_id)


@public.fetchImpl
@ExternalAccount.cached
async def fetch(
    critic: api.critic.Critic,
    external_user_id: Optional[int],
    provider_name: Optional[str],
    user: Optional[api.user.User],
    account_id: Optional[str],
) -> WrapperType:
    conditions = []
    if external_user_id is not None:
        conditions.append("id={external_user_id}")
    else:
        conditions.append("provider={provider_name}")
        if user is not None:
            conditions.append("uid={user}")
        else:
            conditions.append("account={account_id}")
    async with ExternalAccount.query(
        critic,
        conditions,
        external_user_id=external_user_id,
        provider_name=provider_name,
        user=user,
        account_id=account_id,
    ) as result:
        try:
            return await ExternalAccount.makeOne(critic, result)
        except result.ZeroRowsInResult:
            assert provider_name is not None
            raise api.externalaccount.NotFound(
                provider_name, user, account_id
            ) from None


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    user: Optional[api.user.User],
    provider_name: Optional[str],
) -> Sequence[WrapperType]:
    conditions = []
    if user is not None:
        conditions.append("user_id={user}")
    if provider_name is not None:
        conditions.append("provider={provider_name}")
    async with ExternalAccount.query(
        critic, conditions, user=user, provider_name=provider_name
    ) as result:
        return await ExternalAccount.make(critic, result)
