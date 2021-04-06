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

import datetime
from typing import Awaitable, Callable, Sequence, Optional, Iterable

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="reply"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid reply id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised by fetchMany() when invalid reply ids are used."""

    pass


class Reply(api.APIObjectWithId):
    @property
    @abstractmethod
    def id(self) -> int:
        """The reply's unique id"""
        ...

    @property
    @abstractmethod
    def is_draft(self) -> bool:
        """True if the reply is not yet published

        Unpublished replies are not displayed to other users."""
        ...

    @property
    @abstractmethod
    async def comment(self) -> api.comment.Comment:
        """The comment this reply is a reply to

        The comment is returned as an api.comment.Comment object."""
        ...

    @property
    @abstractmethod
    async def author(self) -> api.user.User:
        """The reply's author

        The author is returned as an api.user.User object."""
        ...

    @property
    @abstractmethod
    def timestamp(self) -> datetime.datetime:
        """The reply's timestamp

        The return value is a datetime.datetime object."""
        ...

    @property
    @abstractmethod
    def text(self) -> str:
        """The reply's text"""
        ...


async def fetch(critic: api.critic.Critic, reply_id: int) -> Reply:
    """Fetch the Reply object with the given id"""
    return await fetchImpl.get()(critic, reply_id)


async def fetchMany(
    critic: api.critic.Critic, reply_ids: Iterable[int]
) -> Sequence[Reply]:
    """Fetch multiple Reply objects with the given ids"""
    return await fetchManyImpl.get()(critic, list(reply_ids))


async def fetchAll(
    critic: api.critic.Critic,
    *,
    comment: Optional[api.comment.Comment] = None,
    author: Optional[api.user.User] = None
) -> Sequence[Reply]:
    """Fetch all Reply objects

    If |comment| is not None, only replies to the specified comment are
    included.

    If |author| is not None, only replies authored by the specified user are
    included."""
    return await fetchAllImpl.get()(critic, comment, author)


resource_name = table_name = "replies"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, int], Awaitable[Reply]]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[[api.critic.Critic, Sequence[int]], Awaitable[Sequence[Reply]]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.comment.Comment], Optional[api.user.User]],
        Awaitable[Sequence[Reply]],
    ]
] = FunctionRef()
