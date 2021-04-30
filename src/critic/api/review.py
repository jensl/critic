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

"""The `Review` class with associated exceptions and functions.

Use `fetch()` to fetch a single review object from the database, either
specifying its numeric id or the review Git branch as an
`critic.api.branch.Branch` object.

Use `fetchMany()` to fetch multiple review objects specifying their numeric ids,
or `fetchAll()` to fetch all review objects, optionally filtering the set based
on the repository, the state of the review (see `Review.STATE_VALUES`), and/or
its category (see `Review.CATEGORY_VALUES`)."""

from __future__ import annotations
from abc import abstractmethod

import datetime
import logging
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Optional,
    Literal,
    Collection,
    Sequence,
    Mapping,
    Protocol,
    Iterable,
    Set,
    Union,
    cast,
    overload,
)

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api
from critic.base.types import BooleanWithReason


class Error(api.APIError, object_type="review"):
    """Base exception for all errors related to the Review class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid review id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised by `fetchMany()` when invalid review ids are used."""

    pass


class InvalidBranch(api.InvalidItemError, item_type="branch"):
    """Raised by `fetch()` when an invalid branch is used.

    An "invalid branch" here means a branch that does not have a review
    associated with it."""

    @property
    def branch(self) -> api.branch.Branch:
        return self.value


State = Literal["draft", "open", "closed", "dropped"]
STATE_VALUES: Collection[State] = frozenset(["draft", "open", "closed", "dropped"])
"""Possible review states.

- `draft` The review has not been published yet.
- `open` A published and ongoing review.
- `closed` An accepted and closed review.
- `dropped` An abandoned review."""


def as_state(value: str) -> State:
    if value not in STATE_VALUES:
        raise ValueError(f"invalid review state: {value!r}")
    return cast(State, value)


Category = Literal["incoming", "outgoing", "other"]
CATEGORY_VALUES: Collection[Category] = frozenset(["incoming", "outgoing", "other"])
"""Review categories.

- `incoming` Open reviews in which the effective user is assigned to review
    some or all changes. It does not matter whether the changes are already
    reviewed, as long as the review is still open. It also does not matter
    whether the user also owns the review.
- `outgoing` Unpublished or open reviews owned by the effective user.
- `other` Open reviews that the effective user is associated with that is
    not included in the `incoming` or `outgoing` categories. Typically this
    means the user is watching the reviews."""


def as_category(value: str) -> Category:
    if value not in CATEGORY_VALUES:
        raise ValueError(f"invalid review category: {value!r}")
    return cast(Category, value)


IntegrationState = Literal["planned", "in-progress", "performed", "failed"]
INTEGRATION_STATE_VALUES: Collection[IntegrationState] = frozenset(
    ["planned", "in-progress", "performed", "failed"]
)


def as_integration_state(value: str) -> IntegrationState:
    if value not in INTEGRATION_STATE_VALUES:
        raise ValueError(f"invalid review integration state: {value!r}")
    return cast(IntegrationState, value)


IntegrationStrategy = Literal["fast-forward", "cherry-pick", "rebase", "merge"]
INTEGRATION_STRATEGY_VALUES: Collection[IntegrationStrategy] = frozenset(
    ["fast-forward", "cherry-pick", "rebase", "merge"]
)


def as_integration_strategy(value: str) -> IntegrationStrategy:
    if value not in INTEGRATION_STRATEGY_VALUES:
        raise ValueError(f"invalid review integration strategy: {value!r}")
    return cast(IntegrationStrategy, value)


class Review(api.APIObjectWithId):
    """Representation of a Critic review."""

    @property
    @abstractmethod
    def id(self) -> int:
        """The review's unique numeric id."""
        ...

    @property
    @abstractmethod
    def state(self) -> State:
        """The review's current state."""
        ...

    @property
    @abstractmethod
    async def can_publish(self) -> BooleanWithReason:
        ...

    @property
    @abstractmethod
    async def can_close(self) -> BooleanWithReason:
        ...

    @property
    @abstractmethod
    async def can_drop(self) -> BooleanWithReason:
        ...

    @property
    @abstractmethod
    async def can_reopen(self) -> BooleanWithReason:
        ...

    @property
    @abstractmethod
    async def is_accepted(self) -> bool:
        """True if the review is "accepted", False otherwise.

        Being "accepted" means all changes are marked as reviewed, and there
        are no open issues."""
        ...

    @property
    @abstractmethod
    def summary(self) -> Optional[str]:
        """The review's summary/title, or None"""
        ...

    @property
    @abstractmethod
    def description(self) -> Optional[str]:
        """The review's description, or None."""
        ...

    @property
    @abstractmethod
    async def repository(self) -> api.repository.Repository:
        """The repository containing the review branch.

        The value is a `critic.api.repository.Repository` object."""
        ...

    @property
    @abstractmethod
    async def branch(self) -> Optional[api.branch.Branch]:
        """The review branch.

        The value is a `critic.api.branch.Branch` object."""
        ...

    @property
    @abstractmethod
    async def owners(self) -> Collection[api.user.User]:
        """The users that own the review.

        The value is a set of `critic.api.user.User` objects."""
        ...

    @property
    @abstractmethod
    async def assigned_reviewers(self) -> Collection[api.user.User]:
        """The review's assigned reviewers

        The reviewers are returned as a set of api.user.User objects.

        Assigned reviewers are users that have been (manually or
        automatically) assigned as such. An assigned reviewer may or may not
        also be an active reviewer (a reviewer that has reviewed changes)."""
        ...

    @property
    @abstractmethod
    async def active_reviewers(self) -> Collection[api.user.User]:
        """The review's active reviewers

        The reviewers are returned as a set of api.user.User objects.

        Active reviewers are users that have reviewed changes. An active
        reviewer may or may not also be an assigned reviewer (see above)."""
        ...

    @property
    @abstractmethod
    async def watchers(self) -> Collection[api.user.User]:
        """The review's watchers

        The watchers are returned as a set of api.user.User objects.

        A user is a watcher if he/she is on the list of users that receive
        emails about the review, and is neither an owner nor a reviewer."""
        ...

    @property
    @abstractmethod
    async def users(self) -> Collection[api.user.User]:
        """All users involved in any way in the review"""
        ...

    @property
    async def filters(self) -> Sequence[api.reviewfilter.ReviewFilter]:
        """The review's local filters

        The filters are returned as a list of api.reviewfilter.ReviewFilter
        objects."""
        return await api.reviewfilter.fetchAll(self.critic, review=self)

    @property
    async def events(self) -> Sequence[api.reviewevent.ReviewEvent]:
        """Events affecting this review.

        The value is a list of `critic.api.reviewevent.ReviewEvent` objects."""
        return await api.reviewevent.fetchAll(self.critic, review=self)

    @property
    @abstractmethod
    async def commits(self) -> api.commitset.CommitSet:
        """The set of "reviewable" commits.

        This set never changes when the review branch is rebased, and commits
        are never removed from it. For the set of commits that are actually
        reachable from the review branch, consult the `commits` attribute on
        the `critic.api.branch.Branch` object that is returned by the
        `Review.branch` attribute."""
        ...

    @property
    @abstractmethod
    async def changesets(
        self,
    ) -> Optional[Mapping[api.commit.Commit, api.changeset.Changeset]]:
        """Changesets for each commit in `commits`

        The changesets are returned as a dictionary mapping
        api.commit.Commit objects to api.changeset.Changeset objects."""
        ...

    @property
    @abstractmethod
    async def files(self) -> Collection[api.file.File]:
        """The set of files touched by the changes under review

        This includes any files that have been touched along the way but that
        have not been changed if the tip of the review branch is compared to
        its upstream commit (i.e., where all the changes have been reverted.)
        A special case of this is a file that has been added and subsequently
        deleted again, or added and then renamed. The set simply includes any
        file that in any way has been touched.

        The files are returned as a set of api.file.File objects."""
        ...

    @property
    async def rebases(self) -> Sequence[api.rebase.Rebase]:
        """The rebases of the review branch

        The rebases are returned as a list of api.rebase.Rebase objects,
        ordered chronologically with the most recent rebase first."""
        return await api.rebase.fetchAll(self.critic, review=self)

    @property
    @abstractmethod
    async def pending_rebase(self) -> Optional[api.rebase.Rebase]:
        """The pending rebase of the review branch.

        The values is a `critic.api.rebase.Rebase` object, or None if there
        is no pending rebase."""
        ...

    @property
    @abstractmethod
    async def issues(self) -> Sequence[api.comment.Issue]:
        """The issues in the review

        The issues are returned as a list of api.comment.Issue objects."""
        ...

    @property
    @abstractmethod
    async def open_issues(self) -> Sequence[api.comment.Issue]:
        """The open issues in the review

        The issues are returned as a list of api.comment.Issue objects."""
        ...

    @property
    @abstractmethod
    async def notes(self) -> Sequence[api.comment.Note]:
        """The notes in the review

        The notes are returned as a list of api.comment.Note objects."""
        ...

    @property
    async def first_partition(self) -> api.partition.Partition:
        return await api.partition.create(
            self.critic, await self.commits, await self.rebases
        )

    @property
    async def partitions(self) -> AsyncIterator[api.partition.Partition]:
        partition = await self.first_partition
        while True:
            yield partition
            if partition.following:
                partition = partition.following.partition
            else:
                return

    @abstractmethod
    async def isReviewableCommit(self, commit: api.commit.Commit) -> bool:
        """Return true if the commit is a primary commit in this review

        A primary commit is one that is included in one of the log
        partitions, and not just part of the "actual log" after a rebase of
        the review branch."""
        ...

    class Progress(Protocol):
        """Overall reviewing progress summary.

        The progress is expressed as a number between 0 and 1 representing the
        progress towards marking all changes as reviewed, and the number of
        open issues."""

        @property
        def reviewing(self) -> float:
            """Ratio of reviewed / total changed lines

            0 means nothing has been reviewed and 1 means means everything
            has been reviewed. Modified binary files are counted as if they
            contained a single line."""
            ...

        @property
        def open_issues(self) -> int:
            """Number of open issues"""
            ...

    @property
    @abstractmethod
    async def progress(self) -> Progress:
        """Review progress

        See also |is_accepted| for a simple yes/no answer to whether the
        review has been accepted."""
        ...

    @property
    @abstractmethod
    async def total_progress(self) -> float:
        """Total progress made on a review

        Total progress is expressed as a number between 0 and 1, 1 being
        fully reviewed and 0 being fully pending."""
        ...

    @property
    @abstractmethod
    async def progress_per_commit(self) -> Sequence[CommitChangeCount]:
        """Progress made on a review, grouped by commit

        Returned as a list of CommitChangeCount, where each has the number of
        total changed lines, and the number of reviewed changed lines"""
        ...

    @property
    @abstractmethod
    async def initial_commits_pending(self) -> bool:
        """Return true if the review's initial commits are pending

        This means their corresponding changesets have not yet been added to
        the review, and is only the case temporarily right after the review
        has been created."""
        ...

    @property
    @abstractmethod
    async def pending_update(self) -> Optional[api.branchupdate.BranchUpdate]:
        """The pending update of the review's branch, or None if there isn't one

        If not None, this is always the last api.branchupdate.BranchUpdate
        object in the review branch's 'updates' list.  The actual branch will
        have been updated, but the commits added to the branch have not yet
        been added to the review, and no emails will have been sent about it
        to reviewers and watchers yet."""
        ...

    @property
    @abstractmethod
    async def tags(self) -> Collection[api.reviewtag.ReviewTag]:
        """Return the review tags for the current user

        The tags are returned as a set of api.reviewtag.ReviewTag objects. If
        there is no current user, an empty set is returned."""
        ...

    @property
    @abstractmethod
    async def last_changed(self) -> datetime.datetime:
        """Return the timestamp of the most recent change of this review

        The timestamp is returned as a datetime.datetime object.

        Specifically, this is the timestamp of the most recently recorded
        review event."""
        ...

    @abstractmethod
    async def prefetchCommits(self) -> None:
        """Prefetch all commits that are referenced from this review

        This is an optimization if all or most of those commits will be used
        later."""
        ...

    @property
    async def pings(self) -> Sequence[api.reviewping.ReviewPing]:
        """All pings of this review.

        The value is a chronological list of `critic.api.reviewping.ReviewPing`
        objects."""
        return await api.reviewping.fetchAll(self.critic, self)

    class Integration(Protocol):
        @property
        def target_branch(self) -> api.branch.Branch:
            ...

        @property
        def commits_behind(self) -> Optional[int]:
            """Number of commits the review branch is behind the target branch.

            This is the number of commits reachable from the target branch that
            are not reachable from the review branch."""
            ...

        @property
        def state(self) -> IntegrationState:
            ...

        @property
        def squashed(self) -> bool:
            ...

        @property
        def autosquashed(self) -> bool:
            ...

        @property
        def strategy_used(self) -> Optional[IntegrationStrategy]:
            """Strategy used to integrate the changes.

            The value is a string from the `STRATEGY_VALUES` set, or `None` if
            the integration has not been attempted yet. If the integration has
            failed, this is the"""
            ...

        @property
        def conflicts(self) -> Collection[api.file.File]:
            """Files in which conflicts are expected.

            The value is a set of api.file.File objects.

            This is an estimation of what would happen should the integration
            be attempted right now. An integration can still be attempted if
            this list is not empty, and may in theory still succeed."""
            ...

        @property
        def error_message(self) -> Optional[str]:
            ...

    @property
    @abstractmethod
    async def integration(self) -> Optional[Integration]:
        ...


class CommitChangeCount(Protocol):
    @property
    @abstractmethod
    def commit_id(self) -> int:
        ...

    @property
    @abstractmethod
    def total_changes(self) -> int:
        ...

    @property
    @abstractmethod
    def reviewed_changes(self) -> int:
        ...


@overload
async def fetch(critic: api.critic.Critic, review_id: int, /) -> Review:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, branch: api.branch.Branch) -> Review:
    ...


async def fetch(
    critic: api.critic.Critic,
    review_id: Optional[int] = None,
    /,
    *,
    branch: Optional[api.branch.Branch] = None,
) -> Review:
    """Fetch a `Review` object by review id or branch.

    Exactly one of the `review_id` and `branch` arguments can be used (i.e. be
    not None).

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        review_id (int): Numeric id of the review to fetch.
        branch (critic.api.branch.Branch): the branch whose associated review
            to fetch.

    Returns:
        A `Review` object.

    Raises:
        InvalidId: The `review_id` is not a valid review id.
        InvalidBranch: The `branch` does not have a review associated with it.
    """

    return await fetchImpl.get()(critic, review_id, branch)


async def fetchMany(
    critic: api.critic.Critic, review_ids: Iterable[int]
) -> Sequence[Review]:
    """Fetch many `Review` objects by review ids.

    Arguments:
        critic (critic.api.critic.Critic): The current session.
        review_ids (int[]): Iterable of review ids.

    Returns:
        A list of `Review` objects in the same order as in `review_ids`.

    Raises:
        InvalidIds: One or more ids in `review_ids` is not a valid review id.
        AccessDenied: The current user is not allowed to access the repository
            of at least one of the requested reviews."""

    return await fetchManyImpl.get()(critic, list(review_ids))


async def fetchAll(
    critic: api.critic.Critic,
    *,
    repository: Optional[api.repository.Repository] = None,
    state: Optional[Union[State, Iterable[State]]] = None,
    category: Optional[Category] = None,
) -> Sequence[Review]:
    """Fetch all `Review` objects matching the search parameters.

    With no search parameters, all `Review` objects for reviews in the system
    are returned. Depending on the system, this may be a very expensive request.

    Arguments:
        critic: The current session.
        repository: A `critic.api.repository.Repository` object limiting the
                    result to reviews associated with branches in the given
                    repository.
        state: A string or set of strings limiting the result to reviews in the
               specified state or states. See `Review.STATE_VALUES` for possible
               states.
        category: A string limiting the result to reviews in the specified
                  category. See `Review.CATEGORY_VALUES` for available
                  categories.

    Returns:
        A list of `Review` objects."""

    states: Optional[Set[State]]
    if state is not None:
        states = set()
        if isinstance(state, str):
            states.add(cast(State, state))
        else:
            states.update(state)
    else:
        states = None

    return await fetchAllImpl.get()(critic, repository, states, category)


resource_name = table_name = "reviews"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[api.branch.Branch]],
        Awaitable[Review],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[[api.critic.Critic, Sequence[int]], Awaitable[Sequence[Review]]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            Optional[Set[State]],
            Optional[Category],
        ],
        Awaitable[Sequence[Review]],
    ]
] = FunctionRef()
