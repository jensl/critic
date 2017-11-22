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

import datetime
from typing import Optional, Iterable, Sequence, FrozenSet, Literal, cast

from critic import api


class Error(api.APIError, object_type="review event"):
    """Base exception for all errors related to the `ReviewEvent` class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid review event id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised by `fetchMany()` when invalid review event ids are used."""

    pass


EventType = Literal[
    "created",
    "ready",
    "published",
    "closed",
    "dropped",
    "reopened",
    "pinged",
    "branchupdate",
    "batch",
]
EVENT_TYPES: FrozenSet[EventType] = frozenset(
    {
        "created",
        "ready",
        "published",
        "closed",
        "dropped",
        "reopened",
        "pinged",
        "branchupdate",
        "batch",
    }
)
"""Review event types.

- `created` The review was created.
- `ready` The review is "ready" (its initial commits have been processed).
- `published` The review was published.
- `closed` The review was closed.
- `dropped` The review was dropped.
- `reopened` The review was reopened.
- `pinged` The review was pinged.
- `branchupdate` The review branch was updated.
- `batch` A batch of changes (e.g. comments or marking of code as reviewed)
        were published."""


def as_event_type(value: str) -> EventType:
    if value not in EVENT_TYPES:
        raise ValueError(f"invalid review event type: {value!r}")
    return cast(EventType, value)


class ReviewEvent(api.APIObject):
    """Representation of a review event.

    For a list of event types, see `ReviewEvent.EVENT_TYPES`."""

    def __str__(self) -> str:
        return str(self._impl)

    @property
    def id(self) -> int:
        """The event's unique id"""
        return self._impl.id

    @property
    async def review(self) -> api.review.Review:
        """The affected review.

        The value is a `critic.api.review.Review` object."""
        return await self._impl.getReview(self.critic)

    @property
    async def user(self) -> Optional[api.user.User]:
        """The user that triggered the event.

        The value is a `critic.api.user.User` object, or None if the event was
        triggered by the system independently of any direct user interaction.
        """
        return await self._impl.getUser(self.critic)

    @property
    def type(self) -> EventType:
        """The type of event.

        The value is one of the strings in `ReviewEvent.EVENT_TYPES`."""
        return self._impl.type

    @property
    def timestamp(self) -> datetime.datetime:
        """The time at which the event occurred.

        The value is a `datetime.datetime` object."""
        return self._impl.timestamp

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


async def fetch(critic: api.critic.Critic, event_id: int) -> ReviewEvent:
    """Fetch a `ReviewEvent` object by event id.

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        event_id (int): The numeric event id.

    Returns:
        A `ReviewEvent` object.

    Raises:
        InvalidId: The `event_id` is not a valid event id."""
    assert isinstance(critic, api.critic.Critic)

    from .impl import reviewevent as impl

    return await impl.fetch(critic, int(event_id))


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
    from .impl import reviewevent as impl

    assert isinstance(critic, api.critic.Critic)
    event_ids = [int(event_id) for event_id in event_ids]

    return await impl.fetchMany(critic, event_ids)


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: api.review.Review = None,
    user: api.user.User = None,
    event_type: EventType = None,
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

    assert isinstance(critic, api.critic.Critic)
    assert review is None or isinstance(critic, api.review.Review)
    assert user is None or isinstance(critic, api.user.User)
    assert not (review is None and user is None)
    if event_type is not None:
        event_type = str(event_type)
        assert event_type in ReviewEvent.EVENT_TYPES

    from .impl import reviewevent as impl

    return await impl.fetchAll(critic, review, user, event_type)


resource_name = table_name = "reviewevents"
