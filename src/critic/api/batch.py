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
from typing import Set, Sequence, Optional, Mapping, Literal, FrozenSet, cast, overload

from critic import api


class Error(api.APIError):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid batch id is used."""

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
    {
        "created_comments",
        "written_replies",
        "resolved_issues",
        "reopened_issues",
        "morphed_comments",
        "reviewed_changes",
        "unreviewed_changes",
    }
)


def as_discard_value(value: str) -> DiscardValue:
    if value not in DISCARD_VALUES:
        raise ValueError(f"Invalid discard value: {value!r}")
    return cast(DiscardValue, value)


class Batch(api.APIObject):
    def __hash__(self) -> int:
        return hash(self._impl)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Batch):
            return False
        return self._impl == other._impl

    @property
    def id(self) -> int:
        """The batch's unique id, or None for unsubmitted changes"""
        return self._impl.id

    @property
    async def is_empty(self) -> bool:
        """True if the batch contains no changes"""
        return await self._impl.isEmpty(self.critic)

    @property
    async def event(self) -> Optional[api.reviewevent.ReviewEvent]:
        """The review event that corresponds to the submission of these changes

           If this object represents currently unsubmitted changes, this
           attribute is None."""
        return await self._impl.getEvent(self.critic)

    @property
    async def review(self) -> api.review.Review:
        """The target review of the changes

           The review is returned as an api.review.Review object."""
        return await self._impl.getReview(self.critic)

    @property
    async def author(self) -> api.user.User:
        """The author of the changes

           The author is returned as an api.user.User object."""
        return await self._impl.getAuthor(self.critic)

    @property
    async def timestamp(self) -> Optional[datetime.datetime]:
        """The time of submission, or None for unsubmitted changes

           The timestamp is returned as a datetime.datetime object."""
        return await self._impl.getTimestamp(self.critic)

    @property
    async def comment(self) -> Optional[api.comment.Comment]:
        """The author's overall comment

           The comment is returned as an api.comment.Note object, or None if the
           author did not provide a comment."""
        return await self._impl.getComment(self.critic)

    @property
    async def created_comments(self) -> Set[api.comment.Comment]:
        """Created comments

           The comments are returned as a set of api.comment.Comment objects."""
        return await self._impl.getCreatedComments(self.critic)

    @property
    async def written_replies(self) -> Set[api.reply.Reply]:
        """Written replies

           The replies are returned as a set of api.reply.Reply objects."""
        return await self._impl.getWrittenReplies(self.critic)

    @property
    async def resolved_issues(self) -> Set[api.comment.Comment]:
        """Resolved issues

           The issues are returned as a set of api.comment.Comment objects. Note
           that the comment objects represent the current state, and that they
           may be api.comment.Note objects, and if they are api.comment.Issue
           objects, that their `state` attribute will not necessarily be
           "resolved"."""
        return await self._impl.getResolvedIssues(self.critic)

    @property
    async def reopened_issues(self) -> Set[api.comment.Comment]:
        """Reopened issues

           The issues are returned as a set of api.comment.Comment objects. Note
           that the comment objects represent the current state, and that they
           may be api.comment.Note objects, and if they are api.comment.Issue
           objects, that their `state` attribute will not necessarily be
           "open"."""
        return await self._impl.getReopenedIssues(self.critic)

    @property
    async def morphed_comments(
        self,
    ) -> Mapping[api.comment.Comment, api.comment.CommentType]:
        """Morphed comments (comments whose types was changed)

           The comments are returned as a dictionary mapping api.comment.Comment
           objects to their new type as a string ("issue" or "note".) Note that
           the comment object itself represents the current state, and its type
           will not necessarily match the new type it's mapped to."""
        return await self._impl.getMorphedComments(self.critic)

    @property
    async def reviewed_file_changes(
        self,
    ) -> Set[api.reviewablefilechange.ReviewableFileChange]:
        """Reviewed file changes

           The reviewed changes are returned as a set of
           api.reviewablefilechange.ReviewableFileChange objects. Note that
           the file changes objects represent the current state, and their
           `reviewed_by` attribute will not necessarily be the author of this
           batch."""
        return await self._impl.getReviewedFileChanges(self.critic)

    @property
    async def unreviewed_file_changes(
        self,
    ) -> Set[api.reviewablefilechange.ReviewableFileChange]:
        """Unreviewed file changes

           The unreviewed changes are returned as a set of
           api.reviewablefilechange.ReviewableFileChange objects. Note that
           the file changes objects represent the current state, and their
           `reviewed_by` attribute will not necessarily be None."""
        return await self._impl.getUnreviewedFileChanges(self.critic)


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
    batch_id: int = None,
    /,
    *,
    event: api.reviewevent.ReviewEvent = None,
) -> Batch:
    """Fetch the Batch object by id or by review event"""
    from .impl import batch as impl

    return await impl.fetch(critic, batch_id, event)


async def fetchAll(
    critic: api.critic.Critic,
    review: api.review.Review = None,
    author: api.user.User = None,
) -> Sequence[Batch]:
    """Fetch all Batch objects

       If |review| is not None, only batches in the specified review are
       returned.

       If |author| is not None, only batches authored by the specified user are
       returned."""
    from .impl import batch as impl

    return await impl.fetchAll(critic, review, author)


async def fetchUnpublished(
    review: api.review.Review, author: api.user.User = None
) -> Batch:
    """Fetch a Batch object representing current unpublished changes

       The Batch object's |id| and |timestamp| objects will be None to signal
       that the object does not represent a real object. If the current user has
       no unpublished changes, the object's |is_empty| attribute will be true.

       Only the currently authenticated user's unpublished changes are
       returned."""
    from .impl import batch as impl

    return await impl.fetchUnpublished(review, author)


resource_name = table_name = "batches"
