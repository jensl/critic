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

from typing import (
    Awaitable,
    Callable,
    Optional,
    Sequence,
    TypeVar,
    Tuple,
    Any,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="repository setting"):
    """Base exception for all errors related to the RepositorySetting class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid repository setting id is used."""

    pass


class NotDefined(Error):
    """Raised when the requested repository setting is not defined."""

    def __init__(self, scope: str, name: str) -> None:
        """Constructor"""
        super().__init__(f"Repository setting not defined: {scope}:{name}")
        self.scope = scope
        self.name = name


class InvalidScope(Error):
    """Raied when an invalid scope is used."""

    def __init__(self, scope: str) -> None:
        """Constructor"""
        super().__init__(f"Invalid scope: {scope!r}")
        self.scope = scope


class InvalidName(Error):
    """Raied when an invalid name is used."""

    def __init__(self, name: str) -> None:
        """Constructor"""
        super().__init__(f"Invalid name: {name!r}")
        self.name = name


class RepositorySetting(api.APIObject):
    """Representation of a repository setting"""

    @property
    def id(self) -> int:
        """The setting's unique id"""
        return self._impl.id

    @property
    async def repository(self) -> api.repository.Repository:
        """The repository this setting affects"""
        return await self._impl.getRepository(self.critic)

    @property
    def scope(self) -> str:
        """The setting's scope"""
        return self._impl.scope

    @property
    def name(self) -> str:
        """The setting's name"""
        return self._impl.name

    @property
    def value(self) -> Any:
        """The setting's value

        The value is stored as JSON but returned in parsed form, and can thus
        be a dictionary, list, string, number, boolean or None."""
        return self._impl.value


@overload
async def fetch(critic: api.critic.Critic, setting_id: int, /) -> RepositorySetting:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    repository: api.repository.Repository,
    scope: str,
    name: str,
) -> RepositorySetting:
    ...


async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int] = None,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
    scope: Optional[str] = None,
    name: Optional[str] = None,
) -> RepositorySetting:
    """Fetch a RepositorySetting object with the given its id or scope and name

    If `setting_id` is not None, `repository`, `scope` and `name` must all be
    None. If `setting_id` is None, `repository`, `scope` and `name` must all be
    non-None.

    Exceptions:
        InvalidId: if `setting_id` is used but the id is not valid.
        NotDefined: if `scope` and `name` are used but no such setting is
                    defined."""
    return await fetchImpl.get()(critic, setting_id, repository, scope, name)


T = TypeVar("T")


async def get(
    critic: api.critic.Critic,
    repository: api.repository.Repository,
    /,
    scope: str,
    name: str,
    *,
    default: T,
) -> Tuple[T, bool]:
    try:
        setting = await fetch(critic, repository=repository, scope=scope, name=name)
    except NotDefined:
        return default, False
    else:
        return setting.value, True


async def fetchAll(
    critic: api.critic.Critic,
    *,
    repository: Optional[api.repository.Repository] = None,
    scope: Optional[str] = None,
) -> Sequence[RepositorySetting]:
    """Fetch RepositorySetting objects for all settings

    If 'repository' is not None, only settings affecting the specified
    repository are fetched.

    If 'scope' is not None, only settings with a matching scope are fetched."""
    return await fetchAllImpl.get()(critic, repository, scope)


resource_name = table_name = "repositorysettings"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.repository.Repository],
            Optional[str],
            Optional[str],
        ],
        Awaitable[RepositorySetting],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            Optional[str],
        ],
        Awaitable[Sequence[RepositorySetting]],
    ]
] = FunctionRef()
