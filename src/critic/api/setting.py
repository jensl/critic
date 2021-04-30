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
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    Sequence,
    TypeVar,
    Tuple,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="setting"):
    """Base exception for all errors related to the Setting class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid setting id is used"""

    pass


class NotDefined(Error):
    """Raised when the requested setting is not defined."""

    def __init__(self, scope: str, name: str) -> None:
        """Constructor"""
        super().__init__("User setting not defined: %s:%s" % (scope, name))
        self.scope = scope
        self.name = name


class InvalidScope(Error):
    """Raied when an invalid scope is used."""

    def __init__(self, scope: str) -> None:
        """Constructor"""
        super().__init__("Invalid scope: %r" % scope)
        self.scope = scope


class InvalidName(Error):
    """Raied when an invalid name is used."""

    def __init__(self, name: str) -> None:
        """Constructor"""
        super().__init__("Invalid name: %r" % name)
        self.name = name


class Setting(api.APIObjectWithId):
    """Representation of a setting"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The setting's unique id"""
        ...

    @property
    @abstractmethod
    def scope(self) -> str:
        """The setting's scope"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The setting's name"""
        ...

    @property
    @abstractmethod
    def value(self) -> Any:
        """The setting's value

        The value is stored as JSON but returned in parsed form, and can thus
        be a dictionary, list, string, number, boolean or None."""
        ...

    @property
    @abstractmethod
    def value_bytes(self) -> Optional[bytes]:
        """The setting's binary blob value, or None"""
        ...

    @property
    @abstractmethod
    async def user(self) -> Optional[api.user.User]:
        """The user this setting is associated with, or None"""
        ...

    @property
    @abstractmethod
    async def repository(self) -> Optional[api.repository.Repository]:
        """The repository this setting is associated with, or None"""
        ...

    @property
    @abstractmethod
    async def branch(self) -> Optional[api.branch.Branch]:
        """The branch this setting is associated with, or None"""
        ...

    @property
    @abstractmethod
    async def review(self) -> Optional[api.review.Review]:
        """The review this setting is associated with, or None"""
        ...

    @property
    @abstractmethod
    async def extension(self) -> Optional[api.extension.Extension]:
        """The extension this setting is associated with, or None"""
        ...


@overload
async def fetch(critic: api.critic.Critic, setting_id: int, /) -> Setting:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    scope: str,
    name: str,
    user: Optional[api.user.User] = None,
    repository: Optional[api.repository.Repository] = None,
    branch: Optional[api.branch.Branch] = None,
    review: Optional[api.review.Review] = None,
    extension: Optional[api.extension.Extension] = None,
) -> Setting:
    ...


async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int] = None,
    *,
    scope: Optional[str] = None,
    name: Optional[str] = None,
    user: Optional[api.user.User] = None,
    repository: Optional[api.repository.Repository] = None,
    branch: Optional[api.branch.Branch] = None,
    review: Optional[api.review.Review] = None,
    extension: Optional[api.extension.Extension] = None,
) -> Setting:
    """Fetch a Setting object with the given its id or scope and name

    If 'setting_id' is not None, 'scope' and 'name' must be None. If
    'setting_id' is None, 'scope' and 'name' must both be non-None.

    Only the effective user's settings can be accessed.

    Exceptions:

      InvalidId: if 'setting_id' is used but the id is not valid.
      NotDefined: if 'scope' and 'name' are used but no such setting is
                  defined."""
    return await fetchImpl.get()(
        critic, setting_id, scope, name, user, repository, branch, review, extension
    )


async def fetchAll(
    critic: api.critic.Critic,
    *,
    scope: Optional[str] = None,
    user: Optional[api.user.User] = None,
    repository: Optional[api.repository.Repository] = None,
    branch: Optional[api.branch.Branch] = None,
    review: Optional[api.review.Review] = None,
    extension: Optional[api.extension.Extension] = None,
) -> Sequence[Setting]:
    """Fetch Setting objects for all settings

    Only the effective user's settings can be accessed.

    If 'scope' is not None, only settings with a matching scope are
    fetched."""
    return await fetchAllImpl.get()(
        critic, scope, user, repository, branch, review, extension
    )


resource_name = table_name = "settings"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[str],
            Optional[str],
            Optional[api.user.User],
            Optional[api.repository.Repository],
            Optional[api.branch.Branch],
            Optional[api.review.Review],
            Optional[api.extension.Extension],
        ],
        Awaitable[Setting],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[str],
            Optional[api.user.User],
            Optional[api.repository.Repository],
            Optional[api.branch.Branch],
            Optional[api.review.Review],
            Optional[api.extension.Extension],
        ],
        Awaitable[Sequence[Setting]],
    ]
] = FunctionRef()
