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

from typing import Any, Mapping, Sequence, Iterable, Union, overload

from critic import api


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
        return self._impl.key

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
    critic: api.critic.Critic, setting_id: int = None, /, *, key: str = None
) -> SystemSetting:
    """Fetch a SystemSetting object with the given id"""
    from .impl import systemsetting as impl

    return await impl.fetch(critic, setting_id, key)


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
    setting_ids: Iterable[int] = None,
    /,
    *,
    keys: Iterable[str] = None,
) -> Sequence[SystemSetting]:
    """Fetch many SystemSetting object with the given ids"""
    from .impl import systemsetting as impl

    return await impl.fetchMany(critic, setting_ids, keys)


async def fetchAll(
    critic: api.critic.Critic, *, prefix: str = None
) -> Sequence[SystemSetting]:
    """Fetch SystemSetting objects for all system settings

       If |prefix| is not None, fetch only settings whose id has the specified
       prefix."""
    from .impl import systemsetting as impl

    assert isinstance(critic, api.critic.Critic)
    if prefix is not None:
        prefix = str(prefix)
    return await impl.fetchAll(critic, prefix)


@overload
async def get(critic: api.critic.Critic, key: str, /) -> object:
    ...


@overload
async def get(critic: api.critic.Critic, /, *, prefix: str) -> Mapping[str, object]:
    ...


async def get(
    critic: api.critic.Critic, key: str = None, *, prefix: str = None
) -> Union[object, Mapping[str, object]]:
    """Fetch a system setting's value"""
    if key is None:
        return {
            setting.key: setting.value
            for setting in await fetchAll(critic, prefix=prefix)
        }
    return (await fetch(critic, key=key)).value


resource_name = table_name = "systemsettings"
