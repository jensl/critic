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

from typing import Optional, Sequence, TypeVar, Tuple, Any, Union, overload

from critic import api


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
    critic: api.critic.Critic, scope_id: int = None, /, *, name: str = None,
) -> ReviewScope:
    from .impl import reviewscope as impl

    return await impl.fetch(critic, scope_id, name)


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    filter: Union[
        api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter
    ] = None,
) -> Sequence[ReviewScope]:
    from .impl import reviewscope as impl

    return await impl.fetchAll(critic, filter)


resource_name = table_name = "reviewscopes"
