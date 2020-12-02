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

from typing import Tuple, Optional, Sequence

from critic import api
from critic.api import reviewscopefilter as public
from . import apiobject

WrapperType = api.reviewscopefilter.ReviewScopeFilter
ArgumentsType = Tuple[int, int, int, str, bool]


class ReviewScopeFilter(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = ["id", "repository", "scope", "path", "included"]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__repository_id,
            self.__scope_id,
            self.path,
            self.included,
        ) = args

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)

    async def getReviewScope(
        self, critic: api.critic.Critic
    ) -> api.reviewscope.ReviewScope:
        return await api.reviewscope.fetch(critic, self.__scope_id)


@public.fetchImpl
@ReviewScopeFilter.cached
async def fetch(critic: api.critic.Critic, filter_id: int) -> WrapperType:
    async with ReviewScopeFilter.query(
        critic, ["id={filter_id}"], filter_id=filter_id
    ) as result:
        return await ReviewScopeFilter.makeOne(critic, result)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, repository: Optional[api.repository.Repository]
) -> Sequence[WrapperType]:
    conditions = []
    if repository:
        conditions.append("repository={repository}")
    async with ReviewScopeFilter.query(
        critic, conditions, repository=repository
    ) as result:
        return await ReviewScopeFilter.make(critic, result)
