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

from typing import Optional, Protocol, Sequence, overload

from critic import api


class Error(api.APIError, object_type="tracked branch"):
    pass


class InvalidId(api.InvalidIdError, Error):
    pass


class NotFound(Error):
    def __init__(self) -> None:
        super().__init__("No matching tracked branch found")


class TrackedBranch(api.APIObject):
    @property
    def id(self) -> int:
        return self._impl.id

    @property
    def is_disabled(self) -> bool:
        return self._impl.is_disabled

    @property
    def name(self) -> str:
        return self._impl.name

    @property
    async def repository(self) -> api.repository.Repository:
        return await self._impl.getRepository(self.critic)

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
    def source(self) -> Source:
        return self._impl.source


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
    trackedbranch_id: int = None,
    /,
    *,
    repository: api.repository.Repository = None,
    name: str = None,
    branch: api.branch.Branch = None,
    review: api.review.Review = None,
) -> TrackedBranch:
    from .impl import trackedbranch as impl

    return await impl.fetch(critic, trackedbranch_id, repository, name, branch, review)


async def fetchAll(
    critic: api.critic.Critic,
    *,
    repository: api.repository.Repository = None,
    include_review_branches: bool = False,
) -> Sequence[TrackedBranch]:
    from .impl import trackedbranch as impl

    return await impl.fetchAll(critic, repository, include_review_branches)


resource_name = table_name = "trackedbranches"
