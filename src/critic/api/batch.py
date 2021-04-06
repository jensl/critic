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
    Sequence,
    Optional,
    Mapping,
    Literal,
    FrozenSet,
    cast,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="batch"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid batch id is used."""

    pass


class InvalidEvent(api.InvalidItemError, Error, item_type="event"):
    """Raised when an invalid review event is used."""

    pass


DiscardValue = Literal[
    "created_comments",
    "written_replies",
    "resolved_issues",
    "reopened_issues",
    "morphed_comments",
    "reviewed_changes",
    "unreviewed_changes",
]
# Value set for the |discard| argument to |ModifyReview.discardChanges()|.
# Each value means discarding the changes identified by the corresponding
# attribute in this class.
DISCARD_VALUES: FrozenSet[DiscardValue] = frozenset(
    [
        "created_comments",
        "written_replies",
        "resolved_issues",
        "reopened_issues",
        "morphed_comments",
        "reviewed_changes",
        "unreviewed_changes",
    ]
)


def as_discard_value(value: str) -> DiscardValue:
    if value not in DISCARD_VALUES:
        raise ValueError(f"Invalid discard value: {value!r}")
    return cast(DiscardValue, value)


class Batch(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        """The batch's unique id, or negative for unsubmitted changes"""
        ...

    @property
    @abstractmethod
    def is_unpublished(self) -> bool:
        """True if the batch represents unpublished changes"""
        ...

    @property
    @abstractmethod
    async def is_empty(self) -> bool:
        """True if the batch contains no changes"""
        ...

    @property
    @abstractmethod
    async def event(self) -> Optional[api.reviewevent.ReviewEvent]:
        """The review event that corresponds to the submission of these changes

        If this object represents currently unsubmitted changes, this
        attribute is None."""
        ...

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:
        """The target review of the changes"""
        ...

    @property
    @abstractmethod
    async def author(self) -> api.user.User:
        """The author of the changes"""
        ...

    @property
    @abstractmethod
    async def timestamp(self) -> Optional[datetime.datetime]:
        """The time of submission, or None for unsubmitted changes"""
        ...

    @property
    @abstractmethod
    async def comment(self) -> Optional[api.comment.Comment]:
        """The author's overall comment, or None"""
        ...

    @property
    @abstractmethod
    async def created_comments(self) -> Collection[api.comment.Comment]:
        """Created comments"""
        ...

    @property
    @abstractmethod
    async def empty_comments(self) -> Collection[api.comment.Comment]:
        """Empty (created) comments

        These comments would not be published, but rather deleted when
        publishing changes if they haven't been deleted manually or
        automatically before then."""
        ...

    @property
    @abstractmethod
    async def written_replies(self) -> Collection[api.reply.Reply]:
        """Written replies

        The replies are returned as a set of api.reply.Reply objects."""
        ...

    @property
    @abstractmethod
    async def empty_replies(self) -> Collection[api.comment.Reply]:
        """Empty (written) replies

        These replies would not be published, but rather deleted when
        publishing changes if they haven't been deleted manually or
        automatically before then."""
        ...

    @property
    @abstractmethod
    async def resolved_issues(self) -> Collection[api.comment.Comment]:
        """Resolved issues

        The issues are returned as a set of api.comment.Comment objects. Note
        that the comment objects represent the current state, and that they
        may be api.comment.Note objects, and if they are api.comment.Issue
        objects, that their `state` attribute will not necessarily be
        "resolved"."""
        ...

    @property
    @abstractmethod
    async def reopened_issues(self) -> Collection[api.comment.Comment]:
        """Reopened issues

        The issues are returned as a set of api.comment.Comment objects. Note
        that the comment objects represent the current state, and that they
        may be api.comment.Note objects, and if they are api.comment.Issue
        objects, that their `state` attribute will not necessarily be
        "open"."""
        ...

    @property
    @abstractmethod
    async def morphed_comments(
        self,
    ) -> Mapping[api.comment.Comment, api.comment.CommentType]:
        """Morphed comments (comments whose types was changed)

        The comments are returned as a dictionary mapping api.comment.Comment
        objects to their new type as a string ("issue" or "note".) Note that
        the comment object itself represents the current state, and its type
        will not necessarily match the new type it's mapped to."""
        ...

    @property
    @abstractmethod
    async def reviewed_file_changes(
        self,
    ) -> Collection[api.reviewablefilechange.ReviewableFileChange]:
        """Reviewed file changes

        The reviewed changes are returned as a set of
        api.reviewablefilechange.ReviewableFileChange objects. Note that
        the file changes objects represent the current state, and their
        `reviewed_by` attribute will not necessarily be the author of this
        batch."""
        ...

    @property
    @abstractmethod
    async def unreviewed_file_changes(
        self,
    ) -> Collection[api.reviewablefilechange.ReviewableFileChange]:
        """Unreviewed file changes

        The unreviewed changes are returned as a set of
        api.reviewablefilechange.ReviewableFileChange objects. Note that
        the file changes objects represent the current state, and their
        `reviewed_by` attribute will not necessarily be None."""
        ...


@overload
async def fetch(critic: api.critic.Critic, batch_id: int, /) -> Batch:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, event: api.reviewevent.ReviewEvent
) -> Batch:
    ...


async def fetch(
    critic: api.critic.Critic,
    batch_id: Optional[int] = None,
    /,
    *,
    event: Optional[api.reviewevent.ReviewEvent] = None,
) -> Batch:
    """Fetch the Batch object by id or by review event"""
    return await fetchImpl.get()(critic, batch_id, event)


async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review] = None,
    author: Optional[api.user.User] = None,
) -> Sequence[Batch]:
    """Fetch all Batch objects

    If |review| is not None, only batches in the specified review are
    returned.

    If |author| is not None, only batches authored by the specified user are
    returned."""
    return await fetchAllImpl.get()(critic, review, author)


async def fetchUnpublished(
    review: api.review.Review, author: Optional[api.user.User] = None
) -> Batch:
    """Fetch a Batch object representing current unpublished changes

    The Batch object's |id| and |timestamp| objects will be None to signal
    that the object does not represent a real object. If the current user has
    no unpublished changes, the object's |is_empty| attribute will be true.

    Only the currently authenticated user's unpublished changes are
    returned."""
    return await fetchUnpublishedImpl.get()(review, author)


resource_name = table_name = "batches"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[api.reviewevent.ReviewEvent]],
        Awaitable[Batch],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.review.Review], Optional[api.user.User]],
        Awaitable[Sequence[Batch]],
    ]
] = FunctionRef()
fetchUnpublishedImpl: FunctionRef[
    Callable[[api.review.Review, Optional[api.user.User]], Awaitable[Batch]]
] = FunctionRef()
