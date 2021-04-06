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

from typing import Any, Awaitable, Callable, Sequence, Iterable, Optional, overload

from critic import api
from critic.api.apiobject import FunctionRef

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


class SystemEvent(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        """The event's unique id"""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Event category"""
        ...

    @property
    @abstractmethod
    def key(self) -> str:
        """Event key"""
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        """Event title"""
        ...

    @property
    @abstractmethod
    def data(self) -> Any:
        """Event data"""
        ...

    @property
    @abstractmethod
    def handled(self) -> bool:
        """True if the event has been handled

        Note: Not all events are actually handled in any way. For those that
        are not, this attribute is always False."""
        ...


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
    event_id: Optional[int] = None,
    *,
    category: Optional[str] = None,
    key: Optional[str] = None,
) -> SystemEvent:
    """Fetch a SystemEvent object with the given id

    Alternatively, fetch the most recent event with the given category and
    key."""
    api.PermissionDenied.raiseUnlessSystem(critic)
    return await fetchImpl.get()(critic, event_id, category, key)


async def fetchMany(
    critic: api.critic.Critic, event_ids: Iterable[int]
) -> Sequence[SystemEvent]:
    """Fetch many SystemEvent objects"""
    api.PermissionDenied.raiseUnlessSystem(critic)
    return await fetchManyImpl.get()(critic, list(event_ids))


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    category: str,
    key: Optional[str] = None,
    pending: bool = False,
) -> Sequence[SystemEvent]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    pending: bool = False,
) -> Sequence[SystemEvent]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    *,
    category: Optional[str] = None,
    key: Optional[str] = None,
    pending: bool = False,
) -> Sequence[SystemEvent]:
    """Fetch SystemEvent objects for all system events

    If |category| is not None, fetch only events whose category has the
    specified value. If |key| is not None, fetch only events whose key has
    the specified value. (Use of |key| is only valid together with
    |category|.)"""
    api.PermissionDenied.raiseUnlessSystem(critic)
    return await fetchAllImpl.get()(critic, category, key, pending)


resource_name = table_name = "systemevents"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[str], Optional[str]],
        Awaitable[SystemEvent],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Sequence[int]],
        Awaitable[Sequence[SystemEvent]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[str], Optional[str], bool],
        Awaitable[Sequence[SystemEvent]],
    ]
] = FunctionRef()
