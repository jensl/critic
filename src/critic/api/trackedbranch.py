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
from datetime import datetime
from typing import Awaitable, Callable, Optional, Protocol, Sequence, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="tracked branch"):
    pass


class InvalidId(api.InvalidIdError, Error):
    pass


class NotFound(Error):
    def __init__(self) -> None:
        super().__init__("No matching tracked branch found")


class TrackedBranch(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    @property
    @abstractmethod
    def is_disabled(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_forced(self) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    async def repository(self) -> api.repository.Repository:
        ...

    @property
    async def branch(self) -> Optional[api.branch.Branch]:
        """The local branch that tracks a remote branch, or None

        The branch is returned as an api.branch.Branch object.

        None may be returned if the tracking has just been created, and has
        not been updated yet, or if the tracking is disabled and the local
        branch has been deleted."""
        try:
            return await api.branch.fetch(
                self.critic, repository=await self.repository, name=self.name
            )
        except api.branch.InvalidName:
            return None

    class Source(Protocol):
        @property
        def url(self) -> str:
            ...

        @property
        def name(self) -> str:
            ...

    @property
    @abstractmethod
    def source(self) -> Source:
        ...

    @property
    @abstractmethod
    def last_update(self) -> Optional[datetime]:
        ...

    @property
    @abstractmethod
    def next_update(self) -> Optional[datetime]:
        ...


@overload
async def fetch(critic: api.critic.Critic, trackedbranch_id: int, /) -> TrackedBranch:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, repository: api.repository.Repository, name: str
) -> TrackedBranch:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, branch: api.branch.Branch
) -> TrackedBranch:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, review: api.review.Review
) -> TrackedBranch:
    ...


async def fetch(
    critic: api.critic.Critic,
    trackedbranch_id: Optional[int] = None,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
    name: Optional[str] = None,
    branch: Optional[api.branch.Branch] = None,
    review: Optional[api.review.Review] = None,
) -> TrackedBranch:
    return await fetchImpl.get()(
        critic, trackedbranch_id, repository, name, branch, review
    )


async def fetchAll(
    critic: api.critic.Critic,
    *,
    repository: Optional[api.repository.Repository] = None,
    include_review_branches: bool = False,
) -> Sequence[TrackedBranch]:
    return await fetchAllImpl.get()(critic, repository, include_review_branches)


resource_name = table_name = "trackedbranches"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.repository.Repository],
            Optional[str],
            Optional[api.branch.Branch],
            Optional[api.review.Review],
        ],
        Awaitable[TrackedBranch],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            bool,
        ],
        Awaitable[Sequence[TrackedBranch]],
    ]
] = FunctionRef()
