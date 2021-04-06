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
from abc import abstractmethod

from typing import Awaitable, Callable, Collection, Sequence, Optional

from critic import api
from critic.api.apiobject import FunctionRef
from .repositoryfilter import FilterType


class Error(api.APIError, object_type="review filter"):
    """Base exception for all errors related to the User class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid repository filter id is used"""

    pass


class ReviewFilter(api.APIObjectWithId):
    """Representation of a review filter

    A review filter is a filter that applies to a single review only."""

    @property
    @abstractmethod
    def id(self) -> int:
        """The review filter's unique id"""
        ...

    @property
    @abstractmethod
    async def review(self) -> api.review.Review:
        """The review filter's review"""
        ...

    @property
    @abstractmethod
    async def subject(self) -> api.user.User:
        """The filter's subject

        The subject is the user that the filter applies to."""
        ...

    @property
    @abstractmethod
    def type(self) -> FilterType:
        """The filter's type

        The type is always one of "reviewer", "watcher" and "ignore"."""
        ...

    @property
    @abstractmethod
    def path(self) -> str:
        """The filter's path"""
        ...

    @property
    @abstractmethod
    def default_scope(self) -> bool:
        ...

    @property
    @abstractmethod
    async def scopes(self) -> Collection[api.reviewscope.ReviewScope]:
        ...

    @property
    @abstractmethod
    async def creator(self) -> api.user.User:
        """The review filter's creator

        This is the user that created the review filter, which can be
        different from the filter's subject."""
        ...


async def fetch(
    critic: api.critic.Critic, filter_id: int
) -> api.reviewfilter.ReviewFilter:
    """Fetch a ReviewFilter object with the given filter id"""
    return await fetchImpl.get()(critic, filter_id)


async def fetchAll(
    critic: api.critic.Critic,
    *,
    review: Optional[api.review.Review] = None,
    subject: Optional[api.user.User] = None,
    scope: Optional[api.reviewscope.ReviewScope] = None,
) -> Sequence[ReviewFilter]:
    return await fetchAllImpl.get()(critic, review, subject, scope)


resource_name = table_name = "reviewfilters"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[ReviewFilter]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.review.Review],
            Optional[api.user.User],
            Optional[api.reviewscope.ReviewScope],
        ],
        Awaitable[Sequence[ReviewFilter]],
    ]
] = FunctionRef()
