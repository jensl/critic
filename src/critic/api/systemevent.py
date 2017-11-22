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

from typing import Any, Sequence, Iterable, Optional, overload

from critic import api

resource_name = "systemevents"


class Error(api.APIError, object_type="system event"):
    """Base exception for all errors related to the SystemEvent class"""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised when one or more invalid system event ids is used"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when a single invalid system event id is used"""

    pass


class NotFound(Error):
    def __init__(self, category: str, key: str):
        super().__init__(f"No matching system event found: {category=} {key=}")


class SystemEvent(api.APIObject):
    @property
    def id(self) -> int:
        """The event's unique id"""
        return self._impl.id

    @property
    def category(self) -> str:
        """Event category"""
        return self._impl.category

    @property
    def key(self) -> str:
        """Event key"""
        return self._impl.key

    @property
    def title(self) -> str:
        """Event title"""
        return self._impl.title

    @property
    def data(self) -> Any:
        """Event data"""
        return self._impl.data

    @property
    def handled(self) -> bool:
        """True if the event has been handled

           Note: Not all events are actually handled in any way. For those that
           are not, this attribute is always False."""
        return self._impl.handled


@overload
async def fetch(critic: api.critic.Critic, event_id: int, /) -> SystemEvent:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, category: str, key: str
) -> SystemEvent:
    ...


async def fetch(
    critic: api.critic.Critic,
    event_id: int = None,
    *,
    category: str = None,
    key: str = None,
) -> SystemEvent:
    """Fetch a SystemEvent object with the given id

       Alternatively, fetch the most recent event with the given category and
       key."""
    from .impl import systemevent as impl

    api.PermissionDenied.raiseUnlessSystem(critic)
    return await impl.fetch(critic, event_id, category, key)


async def fetchMany(
    critic: api.critic.Critic, event_ids: Iterable[int]
) -> Sequence[SystemEvent]:
    """Fetch many SystemEvent objects"""
    from .impl import systemevent as impl

    api.PermissionDenied.raiseUnlessSystem(critic)
    return await impl.fetchMany(critic, event_ids)


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    category: str,
    key: str = None,
    pending: bool = False,
) -> Sequence[SystemEvent]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic, /, *, pending: bool = False,
) -> Sequence[SystemEvent]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    *,
    category: str = None,
    key: str = None,
    pending: bool = False,
) -> Sequence[SystemEvent]:
    """Fetch SystemEvent objects for all system events

       If |category| is not None, fetch only events whose category has the
       specified value. If |key| is not None, fetch only events whose key has
       the specified value. (Use of |key| is only valid together with
       |category|.)"""
    from .impl import systemevent as impl

    api.PermissionDenied.raiseUnlessSystem(critic)
    return await impl.fetchAll(critic, category, key, pending)


resource_name = table_name = "systemevents"
