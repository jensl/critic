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

from typing import Iterable, Sequence, overload

from critic import api


class Error(api.APIError, object_type="review tag"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid review tag id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised when multiple invalid review tag ids are used."""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid review tag name is used."""

    pass


class InvalidNames(api.InvalidItemsError, Error, items_type="names"):
    """Raised when multiple invalid review tag names are used."""

    pass


class ReviewTag(api.APIObject):
    @property
    def id(self) -> int:
        return self._impl.id

    @property
    def name(self) -> str:
        return self._impl.name

    @property
    def description(self) -> str:
        return self._impl.description


@overload
async def fetch(critic: api.critic.Critic, reviewtag_id: int, /) -> ReviewTag:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, name: str) -> ReviewTag:
    ...


async def fetch(
    critic: api.critic.Critic, reviewtag_id: int = None, /, *, name: str = None
) -> ReviewTag:
    from .impl import reviewtag as impl

    return await impl.fetch(critic, reviewtag_id, name)


@overload
async def fetchMany(
    critic: api.critic.Critic, reviewtag_ids: Iterable[int], /
) -> Sequence[ReviewTag]:
    ...


@overload
async def fetchMany(
    critic: api.critic.Critic, /, *, names: Iterable[str]
) -> Sequence[ReviewTag]:
    ...


async def fetchMany(
    critic: api.critic.Critic,
    reviewtag_ids: Iterable[int] = None,
    /,
    *,
    names: Iterable[str] = None,
) -> Sequence[ReviewTag]:
    from .impl import reviewtag as impl

    return await impl.fetchMany(critic, reviewtag_ids, names)


async def fetchAll(critic: api.critic.Critic) -> Sequence[ReviewTag]:
    from .impl import reviewtag as impl

    return await impl.fetchAll(critic)


resource_name = table_name = "reviewtags"
