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

from __future__ import annotations

from typing import (
    Awaitable,
    Callable,
    Literal,
    Optional,
    Sequence,
    FrozenSet,
    cast,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="branch"):
    """Base exception for all errors related to the Branch class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid branch id is used."""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid branch name is used."""

    pass


BranchType = Literal["normal", "review"]


class Branch(api.APIObject):
    """Representation of a Git branch, according to Critic

    Critic extends Git's branch concept by adding a heuristically determined
    base branch, and a derived restricted set of commits that belong to the
    branch by (initially) excluding those reachable from the base branch."""

    BRANCH_TYPES = frozenset({"normal", "review"})

    @property
    def id(self) -> int:
        """The branch's unique id"""
        return self._impl.id

    @property
    def type(self) -> BranchType:
        """The branch's type"""
        return self._impl.type

    @property
    def name(self) -> str:
        """The branch's name excluding the 'refs/heads/' prefix"""
        return self._impl.name

    @property
    def ref(self) -> str:
        """The branch's full ref name, including the 'refs/heads/' prefix"""
        return f"refs/heads/{self.name}"

    @property
    async def repository(self) -> api.repository.Repository:
        """The repository that contains the branch

        The repository is returned as an api.repository.Repository object."""
        return await self._impl.getRepository(self.critic)

    @property
    def is_archived(self) -> bool:
        return self._impl.is_archived

    @property
    def is_merged(self) -> bool:
        return self._impl.is_merged

    @property
    def size(self) -> int:
        """The number of commits associated with the branch"""
        return self._impl.size

    @property
    async def base_branch(self) -> Optional[Branch]:
        """The upstream branch which this branch is based on

        Note: This was determined heuristically when the branch was created
              and will not always match expectations.

        The base branch is returned as an api.branch.Branch object, or None
        for branches with no upstream branch (typically at least the master
        branch.)"""
        return await self._impl.getBaseBranch(self.critic)

    @property
    async def head(self) -> api.commit.Commit:
        """The branch's head commit"""
        return await self._impl.getHead(self)

    @property
    async def commits(self) -> api.commitset.CommitSet:
        """The commits belonging to the branch

        The return value is an api.commitset.CommitSet object.

        Note: This set of commits is the commits that are actually reachable
              from the head of the branch.  If the branch is a review branch
              that has been rebased, this is not the same as the commits that
              are considered part of the review."""
        return await self._impl.getCommits(self)

    @property
    async def updates(self) -> Sequence[api.branchupdate.BranchUpdate]:
        """The update log of this branch

        The updates are returned as a list of BranchUpdate objects, ordered
        chronologically with the oldest update first.

        Note: The update log of a branch is cleared if the branch is removed,
              so for a branch that has been created and deleted multiple
              times, the log only goes back to the most recent creation of
              the branch.

        Note: This feature was added in an update of Critic.  In systems
              installed before that update, existing branches will not have a
              complete log.  Such branches will have a log that records them
              as having been created by the system with their then current
              value, all at the point in time when the system was updated to
              a version supporting this feature."""
        return await api.branchupdate.fetchAll(self.critic, branch=self)

    @property
    async def review(self) -> Optional[api.review.Review]:
        """The review associated with this branch

        If this is not a review branch, None is returned.

        The review is returned as an api.review.Review object."""
        try:
            return await api.review.fetch(self.critic, branch=self)
        except api.review.InvalidBranch:
            return None


@overload
async def fetch(
    critic: api.critic.Critic,
    branch_id: Optional[int] = None,
    /,
) -> Branch:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
    name: Optional[str] = None,
) -> Branch:
    ...


async def fetch(
    critic: api.critic.Critic,
    branch_id: Optional[int] = None,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
    name: Optional[str] = None,
) -> Branch:
    """Fetch a Branch object with the given id or name

    When a name is provided, a repository must also be provided."""
    return await fetchImpl.get()(critic, branch_id, repository, name)


Order = Literal["name", "update"]
ORDER_VALUES: FrozenSet[Order] = frozenset(["name", "update"])


def as_order(value: str) -> Order:
    if value not in ORDER_VALUES:
        raise ValueError(f"invalid branch order: {value!r}")
    return cast(Order, value)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
    created_by: Optional[api.user.User] = None,
    updated_by: Optional[api.user.User] = None,
    branch_type: BranchType = "normal",
    exclude_reviewed_branches: bool = False,
    order: Order = "name",
) -> Sequence[Branch]:
    """Fetch Branch objects for all branches

    If |repository| is not None, only fetch branches in the given repository.

    If |created_by| is not None, only fetch branches created by the specified
    user, in chronological order with the most recently created branch first.

    If |updated_by| is not None, only fetch branches updated by the specified
    user, in chronological order with the most recently updated branch first.

    If |branch_type| is "normal", all branches that has no associated review
    are returned. If |branch_type| is "review", all branches with an
    associated review are returned. If |branch_type| is None, all branches
    are returned.

    If |exclude_reviewed_branches| is True, then exclude branches whose tip
    commit belongs to the branch of an open or finished review. Note that the
    review branch and the excluded branch may or may not be the same branch
    in this case.

    If |order| is "name", branches are returned in ascending name order. If
    |order| is "update", branches are returned in order of latest update,
    with the most recently updated branch first."""
    return await fetchAllImpl.get()(
        critic,
        repository,
        created_by,
        updated_by,
        branch_type,
        exclude_reviewed_branches,
        order,
    )


resource_name = table_name = "branches"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.repository.Repository],
            Optional[str],
        ],
        Awaitable[Branch],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            Optional[api.user.User],
            Optional[api.user.User],
            BranchType,
            bool,
            Order,
        ],
        Awaitable[Sequence[Branch]],
    ]
] = FunctionRef()
