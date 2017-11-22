# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

"""The `User` class with associated exceptions and functions.

Use `fetch()` to fetch/lookup a single user entry from the database,
`fetchMany()` to fetch/lookup multiple user entries in a single call, or
`fetchAll()` to fetch all user entries, possibly filtered to include only users
with a certain status (see `User.STATUS_VALUES`).
"""

from __future__ import annotations

from typing import Sequence

from critic import api


class Error(api.APIError, object_type="review ping"):
    """Base exception for all errors related to the ReviewPing class"""

    pass


class InvalidReviewEvent(Error):
    """Raised by `fetch()` if the provided event is not valid.

    The provided event must be of the type "pinged" to be valid."""

    def __init__(self, event: api.reviewevent.ReviewEvent) -> None:
        super().__init__(
            f"Event {event.id} is of type '{event.type}', expected 'pinged'"
        )


class ReviewPing(api.APIObject):
    """Representation of a review ping."""

    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def event(self) -> api.reviewevent.ReviewEvent:
        return await self._impl.getEvent(self.critic)

    @property
    def message(self) -> str:
        return self._impl.message


async def fetch(
    critic: api.critic.Critic, event: api.reviewevent.ReviewEvent
) -> ReviewPing:
    """Fetch a `ReviewPing` object using its corresponding review event.

    Args:
        critic (critic.api.critic.Critic): The current session.
        event (critic.api.reviewevent.ReviewEvent): The corresponding review
             event.

    Returns:
        A `ReviewEvent` object.

    Raises:
        InvalidReviewEvent: The event object is not of type "pinged"."""
    from .impl import reviewping as impl

    return await impl.fetch(critic, event)


async def fetchAll(
    critic: api.critic.Critic, review: api.review.Review
) -> Sequence[ReviewPing]:
    """Fetch `ReviewPing` objects for all pings of a review.

    Args:
        critic (critic.api.critic.Critic): The current session.
        review (critic.api.review.Review): The review whose pings to fetch."""
    from .impl import reviewping as impl

    return await impl.fetchAll(critic, review)


resource_name = table_name = "reviewpings"
id_column = "event"
