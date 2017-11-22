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

from typing import Sequence, Optional, overload

from critic import api


class Error(api.APIError, object_type="user SSH key"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid usersshkey id is used."""

    pass


class UserSSHKey(api.APIObject):
    def __str__(self) -> str:
        return f"{self.type} {self.key}"

    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def user(self) -> api.user.User:
        """The user whose key this is"""
        return await self._impl.getUser(self.critic)

    @property
    def type(self) -> str:
        """The key type (typically "rsa", "dsa", "ecdsa" or "ecdsa25519")"""
        return self._impl.type

    @property
    def key(self) -> str:
        """The actual key, base64-encoded"""
        return self._impl.key

    @property
    def comment(self) -> str:
        """User-provided comment"""
        return self._impl.comment

    @property
    def bits(self) -> int:
        return self._impl.getBits()

    @property
    def fingerprint(self) -> str:
        return self._impl.getFingerprint()


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
    usersshkey_id: int = None,
    /,
    *,
    key_type: str = None,
    key: str = None,
) -> Optional[UserSSHKey]:
    from .impl import usersshkey as impl

    return await impl.fetch(critic, usersshkey_id, key_type, key)


async def fetchAll(
    critic: api.critic.Critic, *, user: api.user.User = None
) -> Sequence[UserSSHKey]:
    from .impl import usersshkey as impl

    return await impl.fetchAll(critic, user)


resource_name = table_name = "usersshkeys"
