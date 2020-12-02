# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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
from typing import Awaitable, Callable, Optional, Sequence, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="branch update"):
    """Base exception for all errors related to the BranchUpdate class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid branch update id is used"""

    pass


class InvalidReviewEvent(Error):
    """Raised when a non-branch update review event is specified"""

    def __init__(self, event: api.reviewevent.ReviewEvent) -> None:
        super().__init__(f"Invalid review event type: {event.type}")
        self.event = event


class BranchUpdate(api.APIObject):
    """Representation of a single update of a Git branch"""

    @property
    def id(self) -> int:
        """The branch update's unique id"""
        return self._impl.id

    @property
    async def branch(self) -> api.branch.Branch:
        """The branch that was updated"""
        return await self._impl.getBranch(self.critic)

    @property
    async def updater(self) -> Optional[api.user.User]:
        """The user that performed the update

        None if this update was performed by the system."""
        return await self._impl.getUpdater(self.critic)

    @property
    async def from_head(self) -> Optional[api.commit.Commit]:
        """The old value of the branch's |head| property

        None if this update represents the branch being created."""
        return await self._impl.getFromHead(self.critic)

    @property
    async def to_head(self) -> api.commit.Commit:
        """The new value of the branch's |head| property"""
        return await self._impl.getToHead(self.critic)

    @property
    async def associated_commits(self) -> api.commitset.CommitSet:
        """The commits that were associated with the branch as of this update

        This does not include any commit that was already associated with
        the branch before the update.

        The return value is an api.commitset.CommitSet object."""
        return await self._impl.getAssociatedCommits(self.critic)

    @property
    async def disassociated_commits(self) -> api.commitset.CommitSet:
        """The commits that were disassociated with the branch as of this update

        The return value is an api.commitset.CommitSet object."""
        return await self._impl.getDisassociatedCommits(self.critic)

    @property
    async def rebase(self) -> Optional[api.rebase.Rebase]:
        """The review branch rebase object, or None

        The rebase is returned as an api.rebase.Rebase object.

        This is None whenever the updated branch is not a review branch (even
        if the update itself was non-fast-forward), and also for all fast-
        forward updates."""
        try:
            return await api.rebase.fetch(self.critic, branchupdate=self)
        except api.rebase.NotARebase:
            return None

    @property
    async def commits(self) -> api.commitset.CommitSet:
        """The set of commits associated with the branch after this update

        The set is returned as an api.commitset.CommitSet object.

        The returned commit set will have |to_head| as its (single) head,
        and include all commits in |associated_commits| (if any), plus any
        other commits that were still associated with the branch after this
        update. None of the commits in |disassociated_commits| are included,
        of course."""
        return await self._impl.getCommits(self.critic)

    @property
    def timestamp(self) -> datetime.datetime:
        """The moment in time when the update was performed

        The timestamp is returned as a datetime.datetime object."""
        return self._impl.timestamp

    @property
    def output(self) -> Optional[str]:
        """The Git hook output of the update"""
        return self._impl.output


@overload
async def fetch(critic: api.critic.Critic, branchupdate_id: int, /) -> BranchUpdate:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, event: api.reviewevent.ReviewEvent
) -> BranchUpdate:
    ...


async def fetch(
    critic: api.critic.Critic,
    branchupdate_id: Optional[int] = None,
    /,
    *,
    event: Optional[api.reviewevent.ReviewEvent] = None,
) -> BranchUpdate:
    """Fetch a BranchUpdate object by id or review event"""
    return await fetchImpl.get()(critic, branchupdate_id, event)


async def fetchMany(
    critic: api.critic.Critic, branchupdate_ids: Sequence[int], /
) -> Sequence[BranchUpdate]:
    """Fetch multiple BranchUpdate object by id"""
    return await fetchManyImpl.get()(critic, branchupdate_ids)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    branch: Optional[api.branch.Branch] = None,
    updater: Optional[api.user.User] = None,
) -> Sequence[BranchUpdate]:
    """Fetch all BranchUpdate objects

    If |branch| is not None, only updates of the specified branch are
    returned.

    If |updater| is not None, only updates performed by the specified user
    are returned.

    The updates are returned as a list of BranchUpdate objects, ordered
    chronologically with the most recent update first."""
    return await fetchAllImpl.get()(critic, branch, updater)


resource_name = table_name = "branchupdates"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[api.reviewevent.ReviewEvent]],
        Awaitable[BranchUpdate],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Sequence[int]],
        Awaitable[Sequence[BranchUpdate]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.branch.Branch], Optional[api.user.User]],
        Awaitable[Sequence[BranchUpdate]],
    ]
] = FunctionRef()
