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
    Awaitable,
    Callable,
    Sequence,
    Iterable,
    Optional,
    FrozenSet,
    Protocol,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="reviewable file change"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid reviewable file change id is used"""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised when invalid reviewable file change ids are used"""

    pass


class InvalidChangeset(Error):
    """Raised when fetchAll() is called with an invalid changeset"""

    def __init__(self, changeset: api.changeset.Changeset) -> None:
        super(InvalidChangeset, self).__init__(
            "Changeset has no reviewable changes: %d" % changeset.id
        )
        self.changeset = changeset


class ReviewableFileChange(api.APIObject):
    """Representation of changes to a file, to be reviewed"""

    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def review(self) -> api.review.Review:
        return await self._impl.getReview(self.critic)

    @property
    async def changeset(self) -> api.changeset.Changeset:
        """The changeset that the change is part of

        The changeset is returned as an api.changeset.Changeset object. Note
        that this changeset is always of a single commit, and that this
        commit will be included in a partition in the review (meaning it will
        not be part of a rebased version of the review branch.)"""
        return await self._impl.getChangeset(self.critic)

    @property
    async def file(self) -> api.file.File:
        """The file that was changed

        The file is returned as an api.file.File object."""
        return await self._impl.getFile(self.critic)

    @property
    async def scope(self) -> Optional[api.reviewscope.ReviewScope]:
        return await self._impl.getReviewScope(self.critic)

    @property
    def deleted_lines(self) -> int:
        """Number of deleted or modified lines

        In other words, number of lines in the old version of the file that
        are not present in the new version of the file."""
        return self._impl.deleted_lines

    @property
    def inserted_lines(self) -> int:
        """Number of modified or inserted lines

        In other words, number of lines in the new version of the file that
        were not present in the old version of the file."""
        return self._impl.inserted_lines

    @property
    def is_reviewed(self) -> bool:
        """True if the file change has been marked as reviewed.

        This is true if any user has marked this change as reviewed and
        submitted the changes. To check whether the current user has, look for
        the user in the set returned by `reviewed_by`."""
        return self._impl.is_reviewed

    @property
    async def reviewed_by(self) -> FrozenSet[api.user.User]:
        """The user or users that reviewed the changes

        The value is a set of api.user.User objects, empty if the change has not
        been reviewed yet."""
        return await self._impl.getReviewedBy(self.critic)

    @property
    async def assigned_reviewers(self) -> FrozenSet[api.user.User]:
        """The users that are assigned to review the changes

        The reviewers are returned as a set of api.user.User objects."""
        return await self._impl.getAssignedReviewers(self.critic)

    class DraftChanges(Protocol):
        """Draft changes to file change state"""

        @property
        def author(self) -> api.user.User:
            """The author of these draft changes

            The author is returned as an api.user.User object."""
            ...

        @property
        def new_is_reviewed(self) -> bool:
            """New value for the |is_reviewed| attribute"""
            ...

    @property
    async def draft_changes(self) -> Optional[ReviewableFileChange.DraftChanges]:
        """The file change's current draft changes

        The draft changes are returned as a ReviewableFileChange.DraftChanges
        object, or None if the current user has no unpublished changes to
        this file change."""
        return await self._impl.getDraftChanges(self.critic)


async def fetch(
    critic: api.critic.Critic, filechange_id: int, /
) -> ReviewableFileChange:
    """Fetch a single reviewable file change by its unique id"""
    return await fetchImpl.get()(critic, filechange_id)


async def fetchMany(
    critic: api.critic.Critic, filechange_ids: Iterable[int], /
) -> Sequence[ReviewableFileChange]:
    """Fetch multiple reviewable file change by their unique ids"""
    return await fetchManyImpl.get()(critic, list(filechange_ids))


async def fetchAll(
    review: api.review.Review,
    *,
    changeset: Optional[api.changeset.Changeset] = None,
    file: Optional[api.file.File] = None,
    assignee: Optional[api.user.User] = None,
    is_reviewed: Optional[bool] = None,
) -> Sequence[ReviewableFileChange]:
    """Fetch all reviewable file changes in a review

    If a |changeset| is specified, fetch only file changes that are part of
    that changeset.

    If a |file| is specified, fetch only file changes in that file.

    If a |assignee| is specified, fetch only file changes that the specified
    user is assigned to review.

    If |is_reviewed| is specified (not |None|), fetch only file changes that
    are marked as reviewed (when |is_reviewed==True|) or not."""
    return await fetchAllImpl.get()(review, changeset, file, assignee, is_reviewed)


resource_name = "reviewablefilechanges"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[ReviewableFileChange]]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Sequence[int]], Awaitable[Sequence[ReviewableFileChange]]
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.review.Review,
            Optional[api.changeset.Changeset],
            Optional[api.file.File],
            Optional[api.user.User],
            Optional[bool],
        ],
        Awaitable[Sequence[ReviewableFileChange]],
    ]
] = FunctionRef()
