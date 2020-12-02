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
    Any,
    Awaitable,
    Callable,
    Mapping,
    Optional,
    Sequence,
    Iterable,
    Union,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="system setting"):
    """Base exception for all errors related to the SystemSetting class"""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised when one or more invalid system setting ids is used"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when a single invalid system setting id is used"""

    pass


class InvalidKey(api.InvalidItemError, Error, item_type="key"):
    pass


class InvalidPrefix(Error):
    """Raised when an invalid prefix is used"""

    def __init__(self, value: str) -> None:
        """Constructor"""
        super().__init__("Invalid system setting prefix: %r" % value)
        self.value = value


class SystemSetting(api.APIObject):
    def __str__(self) -> str:
        return self.key

    @property
    def id(self) -> int:
        """The setting's unique id"""
        return self._impl.id

    @property
    def key(self) -> str:
        """The setting's unique key"""
        return self._impl.key

    @property
    def description(self) -> str:
        """The setting's description"""
        return self._impl.description

    @property
    def is_privileged(self) -> bool:
        return self._impl.is_privileged

    @property
    def value(self) -> Any:
        """The setting's value"""
        return self._impl.value


@overload
async def fetch(critic: api.critic.Critic, setting_id: int, /) -> SystemSetting:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, key: str) -> SystemSetting:
    ...


async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int] = None,
    /,
    *,
    key: Optional[str] = None,
) -> SystemSetting:
    """Fetch a SystemSetting object with the given id"""
    return await fetchImpl.get()(critic, setting_id, key)


@overload
async def fetchMany(
    critic: api.critic.Critic, setting_ids: Iterable[int], /
) -> Sequence[SystemSetting]:
    ...


@overload
async def fetchMany(
    critic: api.critic.Critic, /, *, keys: Iterable[str]
) -> Sequence[SystemSetting]:
    ...


async def fetchMany(
    critic: api.critic.Critic,
    setting_ids: Optional[Iterable[int]] = None,
    /,
    *,
    keys: Optional[Iterable[str]] = None,
) -> Sequence[SystemSetting]:
    """Fetch many SystemSetting object with the given ids"""
    if setting_ids is not None:
        setting_ids = list(setting_ids)
    if keys is not None:
        keys = list(keys)
    return await fetchManyImpl.get()(critic, setting_ids, keys)


async def fetchAll(
    critic: api.critic.Critic, *, prefix: Optional[str] = None
) -> Sequence[SystemSetting]:
    """Fetch SystemSetting objects for all system settings

    If |prefix| is not None, fetch only settings whose id has the specified
    prefix."""
    return await fetchAllImpl.get()(critic, prefix)


async def get(critic: api.critic.Critic, key: str, /) -> object:
    """Fetch a system setting's value"""
    return (await fetch(critic, key=key)).value


async def getPrefixed(
    critic: api.critic.Critic, prefix: str, /
) -> Mapping[str, object]:
    """Fetch a system setting's value"""
    return {
        setting.key: setting.value for setting in await fetchAll(critic, prefix=prefix)
    }


resource_name = table_name = "systemsettings"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[str]], Awaitable[SystemSetting]
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[Sequence[int]], Optional[Sequence[str]]],
        Awaitable[Sequence[SystemSetting]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[[api.critic.Critic, Optional[str]], Awaitable[Sequence[SystemSetting]]]
] = FunctionRef()
