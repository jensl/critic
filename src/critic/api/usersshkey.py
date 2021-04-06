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

from typing import Awaitable, Callable, Sequence, Optional, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="user SSH key"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid usersshkey id is used."""

    pass


class UserSSHKey(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    @abstractmethod
    async def user(self) -> api.user.User:
        """The user whose key this is"""
        ...

    @property
    @abstractmethod
    def type(self) -> str:
        """The key type (typically "rsa", "dsa", "ecdsa" or "ecdsa25519")"""
        ...

    @property
    @abstractmethod
    def key(self) -> str:
        """The actual key, base64-encoded"""
        ...

    @property
    @abstractmethod
    def comment(self) -> str:
        """User-provided comment"""
        ...

    @property
    @abstractmethod
    def bits(self) -> int:
        ...

    @property
    @abstractmethod
    def fingerprint(self) -> str:
        ...


@overload
async def fetch(critic: api.critic.Critic, usersshkey_id: int, /) -> UserSSHKey:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, key_type: str, key: str
) -> Optional[UserSSHKey]:
    ...


async def fetch(
    critic: api.critic.Critic,
    usersshkey_id: Optional[int] = None,
    /,
    *,
    key_type: Optional[str] = None,
    key: Optional[str] = None,
) -> Optional[UserSSHKey]:
    return await fetchImpl.get()(critic, usersshkey_id, key_type, key)


async def fetchAll(
    critic: api.critic.Critic, *, user: Optional[api.user.User] = None
) -> Sequence[UserSSHKey]:
    return await fetchAllImpl.get()(critic, user)


resource_name = table_name = "usersshkeys"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[str], Optional[str]],
        Awaitable[Optional[UserSSHKey]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.user.User]],
        Awaitable[Sequence[UserSSHKey]],
    ]
] = FunctionRef()
