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

from typing import Sequence

from critic import api


class Error(api.APIError, object_type="review scope filter"):
    """Base exception for all errors related to the ReviewScopeFilter class"""


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid review scope filter id is used."""


class ReviewScopeFilter(api.APIObject):
    """Representation of a review scope filter"""

    @property
    def id(self) -> int:
        """The scope's unique id"""
        return self._impl.id

    @property
    async def repository(self) -> api.repository.Repository:
        """The repository in which the filter applies"""
        return await self._impl.getRepository(self.critic)

    @property
    async def scope(self) -> api.reviewscope.ReviewScope:
        """The review scope the filter assigns to changes"""
        return await self._impl.getReviewScope(self.critic)

    @property
    def path(self) -> str:
        return self._impl.path

    @property
    def included(self) -> bool:
        return self._impl.included


async def fetch(critic: api.critic.Critic, filter_id: int, /) -> ReviewScopeFilter:
    from .impl import reviewscopefilter as impl

    return await impl.fetch(critic, filter_id)


async def fetchAll(
    critic: api.critic.Critic, /, *, repository: api.repository.Repository = None
) -> Sequence[ReviewScopeFilter]:
    from .impl import reviewscopefilter as impl

    return await impl.fetchAll(critic, repository)


resource_name = table_name = "reviewscopefilters"
