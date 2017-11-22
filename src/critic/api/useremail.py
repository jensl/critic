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

from typing import FrozenSet, Literal, Sequence, Optional, cast, overload

from .. import api


class Error(api.APIError, object_type="user email"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid useremail id is used."""

    pass


Status = Literal["trusted", "verified", "unverified"]
STATUS_VALUES: FrozenSet[Status] = frozenset(
    {
        # Email address came from a trusted source (or we trust all users) and
        # does not need to be verified.
        "trusted",
        # Email address has been verified.
        "verified",
        # Email address has not been verified. Critic will not send emails to
        # it, except for verification request emails.
        "unverified",
    }
)


def as_status(value: str) -> Status:
    if value not in STATUS_VALUES:
        raise ValueError(f"invalid user email status: {value!r}")
    return cast(Status, value)


class UserEmail(api.APIObject):
    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def user(self) -> api.user.User:
        return await self._impl.getUser(self.critic)

    @property
    def address(self) -> str:
        return self._impl.address

    @property
    def status(self) -> Status:
        return self._impl.status

    @property
    async def is_selected(self) -> bool:
        return self._impl.isSelected(self.critic)

    @property
    def token(self) -> str:
        """Current verification token

           The most recently sent verification email will contain a link that
           contains this token."""
        return self._impl.token


@overload
async def fetch(critic: api.critic.Critic, useremail_id: int, /) -> UserEmail:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, user: api.user.User
) -> Optional[UserEmail]:
    ...


async def fetch(
    critic: api.critic.Critic,
    useremail_id: int = None,
    /,
    *,
    user: api.user.User = None,
) -> Optional[UserEmail]:
    from .impl import useremail as impl

    return await impl.fetch(critic, useremail_id, user)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    user: api.user.User = None,
    status: Status = None,
    selected: bool = None,
) -> Sequence[UserEmail]:
    from .impl import useremail as impl

    return await impl.fetchAll(critic, user, status, selected)


resource_name = table_name = "useremails"
