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

from typing import Awaitable, Callable, Literal, Optional, Sequence, FrozenSet

from critic import api
from .apiobject import FunctionRef


class Error(api.APIError, object_type="access token"):
    """Base exception for all errors related to the AccessToken class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid access token id is used"""

    pass


AccessType = Literal["user", "system", "anonymous"]
ACCESS_TYPES: FrozenSet[AccessType] = frozenset(["user", "system", "anonymous"])


class AccessToken(api.APIObject):
    """Representation of an access token"""

    @property
    def access_type(self) -> AccessType:
        """The type of access granted by this access token"""
        return self._impl.access_type

    @property
    def id(self) -> int:
        """The access token's unique id"""
        return self._impl.id

    @property
    async def user(self) -> api.user.User:
        """The user authenticated by the access token, or None"""
        return await self._impl.getUser(self.critic)

    @property
    def token(self) -> str:
        """The actual secret token"""
        return self._impl.getToken(self.critic)

    @property
    def title(self) -> Optional[str]:
        """The access token's title, or None"""
        return self._impl.title

    @property
    async def profile(self) -> Optional[api.accesscontrolprofile.AccessControlProfile]:
        """The access token's access control profile"""
        return await self._impl.getProfile(self.critic)


async def fetch(critic: api.critic.Critic, token_id: int, /) -> AccessToken:
    """Fetch an AccessToken object with the given token id"""
    return await fetchImpl.get()(critic, token_id)


async def fetchAll(
    critic: api.critic.Critic, /, *, user: Optional[api.user.User] = None
) -> Sequence[AccessToken]:
    """Fetch AccessToken objects for all primary profiles in the system

    A profile is primary if it is not the additional restrictions imposed for
    accesses authenticated with an access token.

    If |user| is not None, return only access tokens belonging to the
    specified user."""
    return await fetchAllImpl.get()(critic, user)


resource_name = table_name = "accesstokens"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[AccessToken]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.user.User]], Awaitable[Sequence[AccessToken]]
    ]
] = FunctionRef()
