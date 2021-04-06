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
import datetime
from typing import (
    Awaitable,
    Callable,
    Collection,
    Optional,
    Iterable,
    Sequence,
    FrozenSet,
    Literal,
    cast,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


EventType = Literal[
    "created",
    "published",
    "closed",
    "dropped",
    "reopened",
    "pinged",
    "assignments",
    "branchupdate",
    "batch",
]
EVENT_TYPES: FrozenSet[EventType] = frozenset(
    [
        "created",
        "published",
        "closed",
        "dropped",
        "reopened",
        "pinged",
        "assignments",
        "branchupdate",
        "batch",
    ]
)
"""Review event types.

- `created` The review was created.
- `published` The review was published.
- `closed` The review was closed.
- `dropped` The review was dropped.
- `reopened` The review was reopened.
- `pinged` The review was pinged.
- `assignments` Reviewers were assigned or unassigned.
- `branchupdate` The review branch was updated.
- `batch` A batch of changes (e.g. comments or marking of code as reviewed)
        were published."""


class Error(api.APIError, object_type="review event"):
    """Base exception for all errors related to the `ReviewEvent` class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid review event id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised by `fetchMany()` when invalid review event ids are used."""

    pass


class NoSuchEvent(Error):
    def __init__(self, review: api.review.Review, event_type: EventType):
        super().__init__(f"Review {review.id} has not been {event_type} yet!")


def as_event_type(value: str) -> EventType:
    if value not in EVENT_TYPES:
        raise ValueError(f"invalid review event type: {value!r}")
    return cast(EventType, value)


class ReviewEvent(api.APIObjectWithId):
    """Representation of a review event.

    For a list of event types, see `ReviewEvent.EVENT_TYPES`."""

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:
        """The affected review."""
        ...

    @property
    @abstractmethod
    async def user(self) -> Optional[api.user.User]:
        """The user that triggered the event.

        The value is None if the event was triggered by the system independently
        of any direct user interaction."""
        ...

    @property
    @abstractmethod
    def type(self) -> EventType:
        """The type of event."""
        ...

    @property
    @abstractmethod
    def timestamp(self) -> datetime.datetime:
        """The time at which the event occurred."""
        ...

    @property
    @abstractmethod
    async def users(self) -> Collection[api.user.User]:
        """Users associated with the review at the time of this event.

        Includes users associated to the review due to this event and any event
        occuring before it."""
        ...

    @property
    async def branchupdate(self) -> Optional[api.branchupdate.BranchUpdate]:
        """The branch update this event represents.

        The value is a `critic.api.branchupdate.BranchUpdate` object, or `None`
        if this event's type is not `"branchupdate"`."""
        if self.type != "branchupdate":
            return None
        return await api.branchupdate.fetch(self.critic, event=self)

    @property
    async def batch(self) -> Optional[api.batch.Batch]:
        """The batch of changes whose publication this event represents.

        The value is a `critic.api.batch.Batch` object, or `None` if this
        event's type is not `"batch"`."""
        if self.type != "batch":
            return None
        return await api.batch.fetch(self.critic, event=self)

    @property
    async def ping(self) -> Optional[api.reviewping.ReviewPing]:
        if self.type != "ping":
            return None
        return await api.reviewping.fetch(self.critic, event=self)


@overload
async def fetch(
    critic: api.critic.Critic,
    event_id: int,
    /,
) -> ReviewEvent:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    review: api.review.Review,
    event_type: Literal["created", "published"],
) -> ReviewEvent:
    ...


async def fetch(
    critic: api.critic.Critic,
    event_id: Optional[int] = None,
    /,
    *,
    review: Optional[api.review.Review] = None,
    event_type: Optional[Literal["created", "published"]] = None,
) -> ReviewEvent:
    """Fetch a `ReviewEvent` object by event id.

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        event_id (int): The numeric event id.

    Returns:
        A `ReviewEvent` object.

    Raises:
        InvalidId: The `event_id` is not a valid event id."""
    return await fetchImpl.get()(critic, event_id, review, event_type)


async def fetchMany(
    critic: api.critic.Critic, event_ids: Iterable[int]
) -> Sequence[ReviewEvent]:
    """Fetch many `ReviewEvent` objects by event ids.

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        event_ids (int[]): Iterable of event ids.

    Returns:
        A list of `ReviewEvent` objects in the same order as in `event_ids`.

    Raises:
        InvalidIds: One or more ids in `event_ids` is not a valid event id."""
    return await fetchManyImpl.get()(critic, list(event_ids))


@overload
async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: api.review.Review,
    user: Optional[api.user.User] = None,
    event_type: Optional[EventType] = None,
) -> Sequence[ReviewEvent]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    *,
    user: api.user.User,
    event_type: Optional[EventType] = None,
) -> Sequence[ReviewEvent]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: Optional[api.review.Review] = None,
    user: Optional[api.user.User] = None,
    event_type: Optional[EventType] = None,
) -> Sequence[ReviewEvent]:
    """Fetch all `ReviewEvent` objects matching the search parameters.

    At least one of `review` and `user` must be specified (and not None).

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        review (critic.api.review.Review): The review whose events to fetch.
        user (critic.api.user.User): The user whose events to fetch.
        event_type (str): The type of events to fetch. See
            `ReviewEvent.EVENT_TYPES`.

    Returns:
        A list of `ReviewEvent` objects."""
    return await fetchAllImpl.get()(critic, review, user, event_type)


resource_name = table_name = "reviewevents"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.review.Review],
            Optional[EventType],
        ],
        Awaitable[ReviewEvent],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[[api.critic.Critic, Sequence[int]], Awaitable[Sequence[ReviewEvent]]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.review.Review],
            Optional[api.user.User],
            Optional[EventType],
        ],
        Awaitable[Sequence[ReviewEvent]],
    ]
] = FunctionRef()
