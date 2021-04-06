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
from abc import abstractmethod

import aiohttp.web
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Protocol,
    Sequence,
    overload,
)

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api


class Error(api.APIError, object_type="external account"):
    """Base exception for all errors related to the ExternalAccount class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid external account id is used"""

    pass


class NotFound(Error):
    """Raised when an unknown (provider_name, user/account_id) pair is used"""

    def __init__(
        self,
        provider_name: str,
        user: Optional[api.user.User],
        account_id: Optional[str],
    ):
        """Constructor"""
        super().__init__(
            "Invalid external account: %r/%r" % (provider_name, user or account_id)
        )
        self.provider_name = provider_name
        self.user = user
        self.account_id = account_id


class Provider(Protocol):
    @property
    def configuration(self) -> Any:
        ...

    def getTitle(self) -> str:
        ...

    def getAccountIdDescription(self) -> str:
        ...

    def getAccountURL(self, account_id: str) -> Optional[str]:
        ...

    async def start(
        self, critic: api.critic.Critic, req: aiohttp.web.BaseRequest
    ) -> None:
        ...

    async def finish(
        self, critic: api.critic.Critic, req: aiohttp.web.BaseRequest
    ) -> None:
        ...


class ExternalAccount(api.APIObjectWithId):
    """Representation of an external account used for authentication"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The external account representation's unique id

        This id is internal to Critic; representing Critic's record of the
        external account. The external account will invariable have another
        id, numeric or not, which is returned by the |account_id|
        attribute."""
        ...

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether the external provider is (still) enabled

        If False, this external account can not be used to authenticate
        a user in this Critic system."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """The external authentication provider's internal name"""
        ...

    @property
    @abstractmethod
    def provider_title(self) -> Optional[str]:
        """The external authentication provider's title

        The title is structured to make sense as the X in the expressions
        "Sign in using your X" and "the X Y" (with Y being the accound id of
        the account). For example, a reasonable title could be "Critic
        account", if Critic was the external authentication provider, leading
        to the expressions "Sign in using your Critic account" and "the
        Critic account Y".

        This will be None if the provider is not enabled."""
        ...

    @property
    @abstractmethod
    def provider(self) -> Optional[Provider]:
        """The internal auth.Provider instance, or None

        None is returned if the provider is no longer enabled in system
        configuration (or no longer present.)"""
        ...

    @property
    @abstractmethod
    def account_id(self) -> str:
        """The external account id"""
        ...

    @property
    @abstractmethod
    def account_username(self) -> Optional[str]:
        """The external account's username, or None'"""
        ...

    @property
    @abstractmethod
    def account_fullname(self) -> Optional[str]:
        """The external account's full name, or None'"""
        ...

    @property
    @abstractmethod
    def account_email(self) -> Optional[str]:
        """The external account's email address, or None'"""
        ...

    @property
    @abstractmethod
    def account_url(self) -> Optional[str]:
        """The external account's URL, or None

        If the external authentication provider has a main page for the
        account, this is its URL. It's meaningful to point a user towards
        this URL for more information about the account.

        None is returned if there is no such main page."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True if this external account is connected to a Critic user

        If True, the |user| attribute returns the user it is connected to."""
        ...

    @property
    @abstractmethod
    async def user(self) -> Optional[api.user.User]:
        """The Critic user connected to this external account, or None

        The connected user is returned as an api.user.User object.

        This is the user that can sign into Critic using the external
        account, if there is one."""
        ...


@overload
async def fetch(critic: api.critic.Critic, external_user_id: int, /) -> ExternalAccount:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, provider_name: str, user: api.user.User
) -> ExternalAccount:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, provider_name: str, account_id: str
) -> ExternalAccount:
    ...


async def fetch(
    critic: api.critic.Critic,
    external_user_id: Optional[int] = None,
    /,
    *,
    provider_name: Optional[str] = None,
    user: Optional[api.user.User] = None,
    account_id: Optional[str] = None,
) -> ExternalAccount:
    """Fetch an external account representation given its unique id"""
    return await fetchImpl.get()(
        critic, external_user_id, provider_name, user, account_id
    )


async def fetchAll(
    critic: api.critic.Critic,
    *,
    user: Optional[api.user.User] = None,
    provider_name: Optional[str] = None,
) -> Sequence[ExternalAccount]:
    """Fetch all external account representations

    If |user| is not None, fetch only external accounts connected to the
    given user."""
    return await fetchAllImpl.get()(critic, user, provider_name)


resource_name = table_name = "externalaccounts"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[str],
            Optional[api.user.User],
            Optional[str],
        ],
        Awaitable[ExternalAccount],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.user.User],
            Optional[str],
        ],
        Awaitable[Sequence[ExternalAccount]],
    ]
] = FunctionRef()
