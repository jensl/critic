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
from abc import ABC, abstractmethod

import datetime
from typing import (
    Awaitable,
    Callable,
    Literal,
    FrozenSet,
    Optional,
    Protocol,
    Sequence,
    Iterable,
    Union,
    cast,
    overload,
)

from critic import api
from .apiobject import FunctionRef


class Error(api.APIError, object_type="comment"):
    pass


class InvalidId(api.apierror.InvalidIdError, Error):
    """Raised when an invalid comment id is used."""

    pass


class InvalidIds(api.apierror.InvalidIdsError, Error):
    """Raised by fetchMany() when invalid comment ids are used."""

    pass


class InvalidLocation(Error):
    """Raised when attempting to specify an invalid comment location"""

    pass


CommentType = Literal["issue", "note"]
COMMENT_TYPE_VALUES: FrozenSet[CommentType] = frozenset(["issue", "note"])


def as_comment_type(value: str) -> CommentType:
    if value not in COMMENT_TYPE_VALUES:
        raise ValueError(f"invalid comment type: {value!r}")
    return cast(CommentType, value)


class Comment(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        """The comment's unique id"""
        ...

    @property
    @abstractmethod
    def type(self) -> CommentType:
        """The comment's type

        The type is one of "issue" and "note"."""
        ...

    @property
    @abstractmethod
    def is_draft(self) -> bool:
        """True if the comment is not yet published

        Unpublished comments are not displayed to other users."""
        ...

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:

        """The review to which the comment belongs

        The review is returned as an api.review.Review object."""
        ...

    @property
    @abstractmethod
    async def author(self) -> api.user.User:
        """The comment's author

        The author is returned as an api.user.User object."""
        ...

    @property
    @abstractmethod
    def timestamp(self) -> Optional[datetime.datetime]:
        """The comment's timestamp

        The return value is a datetime.datetime object."""
        ...

    @property
    @abstractmethod
    async def location(self) -> Optional[Location]:
        """The location of the comment, or None

        If the comment was made against lines in a commit message, the return
        value is a api.comment.CommitMessageLocation object.  If the comment
        was made against lines in a file version, the return value is
        api.comment.FileVersionLocation object.  Otherwise, the return value
        is None."""
        ...

    @property
    @abstractmethod
    def text(self) -> str:
        """The comment's text"""
        ...

    @property
    async def replies(self) -> Sequence[api.reply.Reply]:
        """The replies to the comment

        The replies are returned as a list of api.reply.Reply objects, order
        by publish time, with the oldest reply first.

        Note that the current user's draft reply, if any, is not included in
        the returned list."""
        return await api.reply.fetchAll(self.critic, comment=self)

    class DraftChanges(Protocol):
        """Draft changes to the comment"""

        @property
        def author(self) -> api.user.User:
            """The author of these draft changes

            The author is returned as an api.user.User object."""
            ...

        @property
        def is_draft(self) -> bool:
            """True if the comment itself is a draft (not published)"""
            ...

        @property
        def reply(self) -> Optional[api.reply.Reply]:
            """The current unpublished reply

            The reply is returned as an api.reply.Reply object, or None if
            there is no current unpublished reply."""
            ...

        @property
        def new_type(self) -> Optional[CommentType]:
            """The new type of an unpublished type change

            The type is returned as a string. Comment.TYPE_VALUES defines the
            set of possible return values."""
            ...

    @property
    @abstractmethod
    async def draft_changes(self) -> Optional[DraftChanges]:
        """The comment's current draft changes

        The draft changes are returned as a Comment.DraftChanges object, or
        None if the current user has no unpublished changes to this comment.

        If the comment is currently an issue, or the current user has an
        unpublished change of the comment's type to issue, the returned
        object will be an Issue.DraftChanges instead."""
        ...

    @property
    def as_issue(self) -> Issue:
        assert self.type == "issue"
        return cast(Issue, self)

    @property
    def as_note(self) -> Note:
        assert self.type == "note"
        return cast(Note, self)


IssueState = Literal["open", "addressed", "resolved"]
ISSUE_STATE_VALUES = frozenset(["open", "addressed", "resolved"])


def as_issue_state(value: str) -> IssueState:
    if value not in ISSUE_STATE_VALUES:
        raise ValueError(f"invalid issue state: {value!r}")
    return cast(IssueState, value)


class Issue(Comment):
    @property
    def type(self) -> CommentType:
        return "issue"

    @property
    @abstractmethod
    def state(self) -> IssueState:
        """The issue's state

        The state is one of the strings "open", "addressed" or "resolved"."""
        ...

    @property
    @abstractmethod
    async def addressed_by(self) -> Optional[api.commit.Commit]:
        """The commit that addressed the issue, or None

        The value is an api.commit.Commit object, or None if the issue's
        state is not "addressed"."""
        ...

    @property
    @abstractmethod
    async def resolved_by(self) -> Optional[api.user.User]:
        """The user that resolved the issue, or None

        The value is an api.user.User object, or None if the issue's state is
        not "resolved"."""
        ...

    class DraftChanges(Comment.DraftChanges, Protocol):
        """Draft changes to the issue"""

        @property
        def new_state(self) -> Optional[IssueState]:
            """The issue's new state

            The new state is returned as a string, or None if the current
            user has not resolved or reopened the issue. Issue.STATE_VALUES
            defines the set of possible return values."""
            ...

        @property
        def new_location(self) -> Optional[Location]:
            """The issue's new location

            The new location is returned as a FileVersionLocation objects, or
            None if the issue has not been reopened, or if it was manually
            resolved rather than addressed and did not need to be relocated
            when being reopened.

            Since only issues in file version locations can be addressed,
            that is the only possible type of new location."""
            ...

    @property
    @abstractmethod
    async def draft_changes(self) -> Optional[DraftChanges]:
        ...


class Note(Comment):
    @property
    def type(self) -> CommentType:
        return "note"


LocationType = Literal["general", "commit-message", "file-version"]
LOCATION_TYPE_VALUES: FrozenSet[LocationType] = frozenset(
    ["general", "commit-message", "file-version"]
)


def as_location_type(value: str) -> LocationType:
    if value not in LOCATION_TYPE_VALUES:
        raise ValueError(f"invalid comment location type: {value!r}")
    return cast(LocationType, value)


class Location(ABC):
    def __len__(self) -> int:
        """Return the the length of the location, in lines"""
        return (self.last_line - self.first_line) + 1

    @property
    @abstractmethod
    def type(self) -> LocationType:
        """The location's type

        The type is one of "commit-message" and "file-version"."""
        ...

    @property
    @abstractmethod
    def first_line(self) -> int:
        """The line number of the first commented line

        Note that line numbers are one-based."""
        ...

    @property
    @abstractmethod
    def last_line(self) -> int:
        """The line number of the last commented line

        Note that line numbers are one-based."""
        ...

    @property
    def as_commit_message(self) -> CommitMessageLocation:
        assert self.type == "commit-message"
        return cast(CommitMessageLocation, self)

    @property
    def as_file_version(self) -> FileVersionLocation:
        assert self.type == "file-version"
        return cast(FileVersionLocation, self)


class CommitMessageLocation(Location):
    @property
    def type(self) -> LocationType:
        """The location's type, "commit-message" """
        return "commit-message"

    @property
    @abstractmethod
    async def commit(self) -> api.commit.Commit:
        """The commit whose message was commented"""
        ...

    @staticmethod
    def make(
        critic: api.critic.Critic,
        first_line: int,
        last_line: int,
        commit: api.commit.Commit,
    ) -> CommitMessageLocation:
        return makeCommitMessageLocationImpl.get()(first_line, last_line, commit)


Side = Literal["old", "new"]


class FileVersionLocation(Location):
    @property
    def type(self) -> LocationType:
        """The location's type, "file-version" """
        return "file-version"

    @property
    @abstractmethod
    async def changeset(self) -> Optional[api.changeset.Changeset]:
        """The changeset containing the comment

        The changeset is returned as an api.changeset.Changeset object.

        If the comment was created while looking at a diff, this will
        initially be that changeset. As additional commits are added to the
        review, this changeset may be "extended" to contain those added
        commits.

        This is the ideal changeset to use to display the comment, unless it
        is an issue that has been addressed, in which case a better changeset
        would be the diff of the commit returned by Issue.addressed_by.

        If the user did not make the comment while looking at a diff but
        rather while looking at a single version of the file, then this
        attribute returns None.

        If this is an object returned by translateTo() called with a
        changeset argument, then this will be that changeset."""
        ...

    @property
    @abstractmethod
    def side(self) -> Optional[Side]:
        """The commented side ("old" or "new") of the changeset

        If the user did not make the comment while looking at a changeset
        (i.e. a diff) but rather while looking at a single version of the
        file, then this attribute returns None."""
        ...

    @property
    @abstractmethod
    async def commit(self) -> Optional[api.commit.Commit]:
        """The commit whose version of the file this location references

        The commit is returned as an api.commit.Commit object.

        If this is an object returned by translateTo() called with a commit
        argument, then this is the commit that was given as an argument to
        it. If this is the primary location of the comment (returned from
        Comment.location) then this is the commit whose version of the file
        the comment was originally made against, or None if the comment was
        made while looking at a diff."""
        ...

    @property
    @abstractmethod
    async def file(self) -> api.file.File:
        """The commented file"""
        ...

    @property
    @abstractmethod
    async def file_information(self) -> api.commit.Commit.FileInformation:
        """Return information about the referenced file version

        Returns an api.commit.Commit.FileInformation object."""
        ...

    @property
    @abstractmethod
    def is_translated(self) -> bool:
        """True if this is a location returned by |translateTo()|"""
        ...

    @overload
    @abstractmethod
    async def translateTo(
        self, *, changeset: api.changeset.Changeset
    ) -> Optional[FileVersionLocation]:
        ...

    @overload
    @abstractmethod
    async def translateTo(
        self, *, commit: api.commit.Commit
    ) -> Optional[FileVersionLocation]:
        ...

    @abstractmethod
    async def translateTo(
        self,
        *,
        changeset: Optional[api.changeset.Changeset] = None,
        commit: Optional[api.commit.Commit] = None,
    ) -> Optional[FileVersionLocation]:
        """Return a translated file version location, or None

        The location is translated to the version of the file in a certain
        commit. If |changeset| is not None, that commit is the changeset's
        |to_commit|, unless the comment is not present there, and otherwise
        the changeset's |from_commit|. If |commit| is not None, that's the
        commit.

        If the comment is not present in the commit, None is returned.

        The returned object's |is_translated| will be True.

        If the |changeset| argument is not None, then the returned object's
        |changeset| will be that changeset, and its |side| will reflect which
        of its |from_commit| and |to_commit| ended up being used. The
        returned object's |commit| will be None.

        If the |commit| argument is not None, the returned object's |commit|
        will be that commit, and its |changeset| and |side| will be None."""
        ...

    # @overload
    # @staticmethod
    # async def make(
    #     critic: api.critic.Critic,
    #     first_line: int,
    #     last_line: int,
    #     file: api.file.File,
    #     changeset: api.changeset.Changeset,
    #     side: Side,
    # ) -> FileVersionLocation:
    #     ...

    # @overload
    # @staticmethod
    # async def make(
    #     critic: api.critic.Critic,
    #     first_line: int,
    #     last_line: int,
    #     file: api.file.File,
    #     commit: api.commit.Commit,
    # ) -> FileVersionLocation:
    #     ...

    @staticmethod
    async def make(
        critic: api.critic.Critic,
        first_line: int,
        last_line: int,
        file: api.file.File,
        changeset: Optional[api.changeset.Changeset] = None,
        side: Optional[Side] = None,
        commit: Optional[api.commit.Commit] = None,
    ) -> FileVersionLocation:
        return await makeFileVersionLocationImpl.get()(
            first_line, last_line, file, changeset, side, commit
        )


async def fetch(critic: api.critic.Critic, comment_id: int) -> Comment:
    """Fetch the Comment object with the given id"""
    return await fetchImpl.get()(critic, comment_id)


async def fetchMany(
    critic: api.critic.Critic, comment_ids: Iterable[int]
) -> Sequence[Comment]:
    """Fetch multiple Comment objects with the given ids"""
    return await fetchManyImpl.get()(critic, list(comment_ids))


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: Optional[api.review.Review] = None,
    author: Optional[api.user.User] = None,
    comment_type: Optional[CommentType] = None,
    state: Optional[IssueState] = None,
    location_type: Optional[LocationType] = None,
    changeset: Optional[api.changeset.Changeset] = None,
    commit: Optional[api.commit.Commit] = None,
    files: Optional[Iterable[api.file.File]] = None,
    addressed_by: Optional[
        Union[api.commit.Commit, api.branchupdate.BranchUpdate]
    ] = None,
) -> Sequence[Comment]:
    """Fetch all Comment objects

    If |review| is not None, only comments in the specified review are
    returned.

    If |author| is not None, only comments created by the specified user are
    returned.

    If |comment_type| is not None, only comments of the specified type are
    returned.

    If |state| is not None, only issues in the specified state are returned.
    This implies type="issue".

    If |location_type| is not None, only issues in the specified type of
    location are returned.

    If |changeset| is not None, only comments against file versions that are
    referenced by the specified changeset are returned. Must be combined with
    |review|, and can not be combined with |commit|.

    If |commit| is not None, only comments against the commit's message or
    file versions referenced by the commit are returned. Must be combined
    with |review|, and can not be combined with |changeset|.

    If |files| is not None, only comments against versions of included files
    are returned. This implies |location_type="file-version"|.

    If |addressed_by| is not None, only issues that are currently marked as
    having been addressed by the specified commit or branch update are
    returned."""
    return await fetchAllImpl.get()(
        critic,
        review,
        author,
        comment_type,
        state,
        location_type,
        changeset,
        commit,
        files,
        addressed_by,
    )


resource_name = table_name = "comments"
value_class = (Comment, Note, Issue)


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[Comment]]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[[api.critic.Critic, Sequence[int]], Awaitable[Sequence[Comment]]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.review.Review],
            Optional[api.user.User],
            Optional[CommentType],
            Optional[IssueState],
            Optional[LocationType],
            Optional[api.changeset.Changeset],
            Optional[api.commit.Commit],
            Optional[Iterable[api.file.File]],
            Optional[Union[api.commit.Commit, api.branchupdate.BranchUpdate]],
        ],
        Awaitable[Sequence[Comment]],
    ]
] = FunctionRef()
makeCommitMessageLocationImpl: FunctionRef[
    Callable[
        [
            int,
            int,
            api.commit.Commit,
        ],
        CommitMessageLocation,
    ]
] = FunctionRef()
makeFileVersionLocationImpl: FunctionRef[
    Callable[
        [
            int,
            int,
            api.file.File,
            Optional[api.changeset.Changeset],
            Optional[Side],
            Optional[api.commit.Commit],
        ],
        Awaitable[FileVersionLocation],
    ]
] = FunctionRef()
