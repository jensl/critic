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
from typing import Callable, Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import auth
from critic.api import externalaccount as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.ExternalAccount
ArgumentsType = Tuple[
    int, Optional[int], str, str, Optional[str], Optional[str], Optional[str]
]


class ExternalAccount(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__user_id,
            self.__provider_name,
            self.__account_id,
            self.__account_username,
            self.__account_fullname,
            self.__account_email,
        ) = args

        provider = auth.Provider.enabled().get(self.__provider_name)

        self.__enabled = provider is not None
        self.__provider_title = provider.getTitle() if provider else None
        self.__account_url = (
            provider.getAccountURL(self.account_id) if provider else None
        )
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def enabled(self) -> bool:
        return self.__enabled

    @property
    def provider_name(self) -> str:
        return self.__provider_name

    @property
    def provider_title(self) -> Optional[str]:
        return self.__provider_title

    @property
    def provider(self) -> Optional[public.Provider]:
        """The internal auth.Provider instance, or None

        None is returned if the provider is no longer enabled in system
        configuration (or no longer present.)"""
        return auth.Provider.enabled().get(self.provider_name)

    @property
    def account_id(self) -> str:
        """The external account id"""
        return self.__account_id

    @property
    def account_username(self) -> Optional[str]:
        """The external account's username, or None'"""
        return self.__account_username

    @property
    def account_fullname(self) -> Optional[str]:
        """The external account's full name, or None'"""
        return self.__account_fullname

    @property
    def account_email(self) -> Optional[str]:
        """The external account's email address, or None'"""
        return self.__account_email

    @property
    def account_url(self) -> Optional[str]:
        """The external account's URL, or None

        If the external authentication provider has a main page for the
        account, this is its URL. It's meaningful to point a user towards
        this URL for more information about the account.

        None is returned if there is no such main page."""
        return self.__account_url

    @property
    def is_connected(self) -> bool:
        """True if this external account is connected to a Critic user

        If True, the |user| attribute returns the user it is connected to."""
        return self.__user_id is not None

    @property
    async def user(self) -> Optional[api.user.User]:
        if self.__user_id is None:
            return None
        return await api.user.fetch(self.critic, self.__user_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    ExternalAccount.getTableName(),
    "id",
    "uid",
    "provider",
    "account",
    "username",
    "fullname",
    "email",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    external_user_id: Optional[int],
    provider_name: Optional[str],
    user: Optional[api.user.User],
    account_id: Optional[str],
) -> PublicType:
    if external_user_id is not None:
        return await ExternalAccount.ensureOne(
            external_user_id, queries.idFetcher(critic, ExternalAccount)
        )

    assert provider_name is not None
    conditions = ["provider={provider_name}"]
    if user is not None:
        conditions.append("uid={user}")
    else:
        conditions.append("account={account_id}")
    return ExternalAccount.storeOne(
        await queries.query(
            critic,
            *conditions,
            provider_name=provider_name,
            user=user,
            account_id=account_id,
        ).makeOne(ExternalAccount, public.NotFound(provider_name, user, account_id))
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    user: Optional[api.user.User],
    provider_name: Optional[str],
) -> Sequence[PublicType]:
    return ExternalAccount.store(
        await queries.query(critic, uid=user, provider=provider_name).make(
            ExternalAccount
        )
    )
