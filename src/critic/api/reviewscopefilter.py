# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2020 the Critic contributors, Opera Software ASA
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

from typing import Awaitable, Callable, Optional, Sequence

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="review scope filter"):
    """Base exception for all errors related to the ReviewScopeFilter class"""


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid review scope filter id is used."""


class ReviewScopeFilter(api.APIObjectWithId):
    """Representation of a review scope filter"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The scope's unique id"""
        ...

    @property
    @abstractmethod
    async def repository(self) -> api.repository.Repository:
        """The repository in which the filter applies"""
        ...

    @property
    @abstractmethod
    async def scope(self) -> api.reviewscope.ReviewScope:
        """The review scope the filter assigns to changes"""
        ...

    @property
    @abstractmethod
    def path(self) -> str:
        ...

    @property
    @abstractmethod
    def included(self) -> bool:
        ...


async def fetch(critic: api.critic.Critic, filter_id: int, /) -> ReviewScopeFilter:
    return await fetchImpl.get()(critic, filter_id)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    repository: Optional[api.repository.Repository] = None,
) -> Sequence[ReviewScopeFilter]:
    return await fetchAllImpl.get()(critic, repository)


resource_name = table_name = "reviewscopefilters"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[ReviewScopeFilter]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.repository.Repository]],
        Awaitable[Sequence[ReviewScopeFilter]],
    ]
] = FunctionRef()
