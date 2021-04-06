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
import logging
from typing import Awaitable, Callable, Literal, Optional, Sequence, cast, overload

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api


class Error(api.APIError, object_type="rebase"):
    """Base exception for all errors related to the Rebase class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid rebase id is used"""

    pass


class NotARebase(Error):
    """Raised by fetch() for branch updates that are not rebases"""

    def __init__(self, branchupdate: api.branchupdate.BranchUpdate) -> None:
        """Constructor"""
        super().__init__("Not a rebase: %r" % branchupdate)
        self.branchupdate = branchupdate


class Rebase(api.APIObjectWithId):
    """Representation of a rebase of a review branch."""

    @property
    @abstractmethod
    def type(self) -> Literal["history-rewrite", "move"]:
        ...

    @property
    @abstractmethod
    def id(self) -> int:
        """The rebases unique numeric id."""
        ...

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:
        """The review whose branch was rebased.

        The value is a `critic.api.review.Review` object."""
        ...

    @property
    @abstractmethod
    def is_pending(self) -> bool:
        ...

    @property
    @abstractmethod
    async def branchupdate(self) -> Optional[api.branchupdate.BranchUpdate]:
        """The record branch update that performed the rebase.

        The value is a `critic.api.branchupdate.BranchUpdate` object."""
        ...

    @property
    @abstractmethod
    async def creator(self) -> api.user.User:
        """The user who performed the rebase.

        The value is a `critic.api.user.User` object."""
        ...

    @property
    def as_history_rewrite(self) -> HistoryRewrite:
        assert self.type == "history-rewrite"
        return cast(HistoryRewrite, self)

    @property
    def as_move_rebase(self) -> MoveRebase:
        assert self.type == "move"
        return cast(MoveRebase, self)


class HistoryRewrite(Rebase):
    """Representation of a history rewrite rebase

    The review branch after a history rewrite rebase is always based on the
    same upstream commit as before it and makes the exact same changes
    relative it, but contains a different set of actual commits."""

    @property
    def type(self) -> Literal["history-rewrite"]:
        return "history-rewrite"


class MoveRebase(Rebase):
    """Representation of a "move" rebase

    A move rebase moves the changes in the review onto a different upstream
    commit."""

    @property
    def type(self) -> Literal["move"]:
        return "move"

    @property
    @abstractmethod
    async def old_upstream(self) -> api.commit.Commit:
        ...

    @property
    @abstractmethod
    async def new_upstream(self) -> api.commit.Commit:
        ...

    @property
    @abstractmethod
    async def equivalent_merge(self) -> Optional[api.commit.Commit]:
        ...

    @property
    @abstractmethod
    async def replayed_rebase(self) -> Optional[api.commit.Commit]:
        ...


@overload
async def fetch(critic: api.critic.Critic, rebase_id: int, /) -> Rebase:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, branchupdate: api.branchupdate.BranchUpdate
) -> Rebase:
    ...


async def fetch(
    critic: api.critic.Critic,
    rebase_id: Optional[int] = None,
    /,
    *,
    branchupdate: Optional[api.branchupdate.BranchUpdate] = None,
) -> Rebase:
    """Fetch a Rebase object with the given id"""
    return await fetchImpl.get()(critic, rebase_id, branchupdate)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    review: Optional[api.review.Review] = None,
    pending: bool = False,
) -> Sequence[Rebase]:
    """Fetch Rebase objects for all rebases

    If a review is provided, restrict the return value to rebases of the
    specified review. If pending is True, fetch only pending rebases,
    otherwise fetch only performed (completed) rebases."""
    return await fetchAllImpl.get()(critic, review, pending)


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[api.branchupdate.BranchUpdate]],
        Awaitable[Rebase],
    ]
] = FunctionRef()

fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.review.Review], bool],
        Awaitable[Sequence[Rebase]],
    ]
] = FunctionRef()


resource_name = "rebases"
table_name = "reviewrebases"
value_class = (Rebase, HistoryRewrite, MoveRebase)
