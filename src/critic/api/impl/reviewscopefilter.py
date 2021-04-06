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

from typing import Callable, Tuple, Optional, Sequence

from critic import api
from critic.api import reviewscopefilter as public
from critic.api.impl.queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId

PublicType = public.ReviewScopeFilter
ArgumentsType = Tuple[int, int, int, str, bool]


class ReviewScopeFilter(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__repository_id,
            self.__scope_id,
            self.__path,
            self.__included,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    async def scope(self) -> api.reviewscope.ReviewScope:
        return await api.reviewscope.fetch(self.critic, self.__scope_id)

    @property
    def path(self) -> str:
        return self.__path

    @property
    def included(self) -> bool:
        return self.__included

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "repository", "scope", "path", "included"
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, filter_id: int) -> PublicType:
    return await ReviewScopeFilter.ensureOne(
        filter_id, queries.idFetcher(critic, ReviewScopeFilter)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, repository: Optional[api.repository.Repository]
) -> Sequence[PublicType]:
    return ReviewScopeFilter.store(
        await queries.query(critic, repository=repository).make(ReviewScopeFilter)
    )
