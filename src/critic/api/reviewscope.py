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

from typing import (
    Awaitable,
    Callable,
    Optional,
    Sequence,
    Union,
    overload,
)

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="review scope"):
    """Base exception for all errors related to the ReviewScope class"""


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid review scope id is used."""


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raied when an invalid review scope name is used."""


class ReviewScope(api.APIObject):
    """Representation of a review scope"""

    @property
    def id(self) -> int:
        """The scope's unique id"""
        return self._impl.id

    @property
    def name(self) -> str:
        """The scope's name"""
        return self._impl.name


@overload
async def fetch(critic: api.critic.Critic, scope_id: int, /) -> ReviewScope:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, name: str) -> ReviewScope:
    ...


async def fetch(
    critic: api.critic.Critic,
    scope_id: Optional[int] = None,
    /,
    *,
    name: Optional[str] = None,
) -> ReviewScope:
    return await fetchImpl.get()(critic, scope_id, name)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    filter: Optional[
        Union[api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter]
    ] = None,
) -> Sequence[ReviewScope]:
    return await fetchAllImpl.get()(critic, filter)


resource_name = table_name = "reviewscopes"

fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, Optional[int], Optional[str]], Awaitable[ReviewScope]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[
                Union[
                    api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter
                ]
            ],
        ],
        Awaitable[Sequence[ReviewScope]],
    ]
] = FunctionRef()
