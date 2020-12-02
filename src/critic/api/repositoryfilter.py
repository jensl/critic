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
    Collection,
    Literal,
    Sequence,
    Optional,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="repository filter"):
    """Base exception for all errors related to the User class."""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid repository filter id is used"""

    pass


FilterType = Literal["reviewer", "watcher", "ignore"]


class RepositoryFilter(api.APIObject):
    """Representation of a repository filter

    A repository filter is a filter that applies to all reviews in a
    repository."""

    @property
    def id(self) -> int:
        """The repository filter's unique id"""
        return self._impl.id

    @property
    async def repository(self) -> api.repository.Repository:
        """The repository filter's repository"""
        return await self._impl.getRepository(self.critic)

    @property
    async def subject(self) -> api.user.User:
        """The filter's subject

        The subject is the user that the filter applies to."""
        return await self._impl.getSubject(self.critic)

    @property
    def type(self) -> FilterType:
        """The filter's type

        The type is always one of "reviewer", "watcher" and "ignore"."""
        return self._impl.type

    @property
    def path(self) -> str:
        """The filter's path"""
        return self._impl.path

    @property
    def default_scope(self) -> bool:
        return self._impl.default_scope

    @property
    async def scopes(self) -> Collection[api.reviewscope.ReviewScope]:
        return await self._impl.getScopes(self)

    @property
    async def delegates(self) -> Collection[api.user.User]:
        """The repository filter's delegates, or None

        The delegates are returned as a frozenset of api.user.User objects.
        If the filter's type is not "reviewer", this attribute's value is
        None."""
        return await self._impl.getDelegates(self)


async def fetch(critic: api.critic.Critic, filter_id: int) -> RepositoryFilter:
    """Fetch a RepositoryFilter object with the given filter id"""
    return await fetchImpl.get()(critic, filter_id)


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    subject: Optional[api.user.User] = None,
    scope: Optional[api.reviewscope.ReviewScope] = None,
) -> Sequence[RepositoryFilter]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    subject: Optional[api.user.User] = None,
    repository: api.repository.Repository,
    file: Optional[api.file.File] = None,
    scope: Optional[api.reviewscope.ReviewScope] = None,
) -> Sequence[RepositoryFilter]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    subject: Optional[api.user.User] = None,
    review: api.review.Review,
    file: Optional[api.file.File] = None,
    scope: Optional[api.reviewscope.ReviewScope] = None,
) -> Sequence[RepositoryFilter]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    subject: Optional[api.user.User] = None,
    repository: Optional[api.repository.Repository] = None,
    review: Optional[api.review.Review] = None,
    file: Optional[api.file.File] = None,
    scope: Optional[api.reviewscope.ReviewScope] = None,
) -> Sequence[RepositoryFilter]:
    return await fetchAllImpl.get()(critic, repository, review, subject, file, scope)


resource_name = table_name = "repositoryfilters"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[RepositoryFilter]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            Optional[api.review.Review],
            Optional[api.user.User],
            Optional[api.file.File],
            Optional[api.reviewscope.ReviewScope],
        ],
        Awaitable[Sequence[RepositoryFilter]],
    ]
] = FunctionRef()
