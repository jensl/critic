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

from typing import Any, Awaitable, Callable, Optional, Sequence, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="branch setting"):
    """Base exception for all errors related to the BranchSetting class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid branch setting id is used."""

    pass


class NotDefined(Error):
    """Raised when the requested branch setting is not defined."""

    def __init__(self, scope: str, name: str) -> None:
        """Constructor"""
        super().__init__(f"Branch setting not defined: {scope}:{name}")
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


class BranchSetting(api.APIObject):
    """Representation of a branch setting"""

    @property
    def id(self) -> int:
        """The setting's unique id"""
        return self._impl.id

    @property
    async def branch(self) -> api.branch.Branch:
        """The branch this setting affects"""
        return await self._impl.getBranch(self.critic)

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
async def fetch(
    critic: api.critic.Critic, setting_id: Optional[int] = None, /
) -> BranchSetting:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, branch: api.branch.Branch, scope: str, name: str
) -> BranchSetting:
    ...


async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int] = None,
    /,
    *,
    branch: Optional[api.branch.Branch] = None,
    scope: Optional[str] = None,
    name: Optional[str] = None,
) -> BranchSetting:
    """Fetch a BranchSetting object with the given its id or scope and name

    If `setting_id` is not None, `branch`, `scope` and `name` must all be
    None. If `setting_id` is None, `branch`, `scope` and `name` must all be
    non-None.

    Exceptions:
        InvalidId: if `setting_id` is used but the id is not valid.
        NotDefined: if `scope` and `name` are used but no such setting is
                    defined."""
    return await fetchImpl.get()(critic, setting_id, branch, scope, name)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    branch: Optional[api.branch.Branch] = None,
    scope: Optional[str] = None,
) -> Sequence[BranchSetting]:
    """Fetch BranchSetting objects for all settings

    If 'branch' is not None, only settings affecting the specified
    branch are fetched.

    If 'scope' is not None, only settings with a matching scope are fetched."""
    return await fetchAllImpl.get()(critic, branch, scope)


resource_name = table_name = "branchsettings"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.branch.Branch],
            Optional[str],
            Optional[str],
        ],
        Awaitable[BranchSetting],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.branch.Branch], Optional[str]],
        Awaitable[Sequence[BranchSetting]],
    ]
] = FunctionRef()
