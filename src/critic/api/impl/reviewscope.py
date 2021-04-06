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

from typing import Callable, Tuple, Optional, Sequence, Union

from critic import api
from critic.api import reviewscope as public
from critic.api.impl.queryhelper import QueryHelper, QueryResult, join
from .apiobject import APIObjectImplWithId

PublicType = public.ReviewScope
ArgumentsType = Tuple[int, str]


class ReviewScope(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__name) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](PublicType.getTableName(), "id", "name")


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, scope_id: Optional[int], name: Optional[str]
) -> PublicType:
    if scope_id is not None:
        return await ReviewScope.ensureOne(
            scope_id, queries.idFetcher(critic, ReviewScope)
        )
    assert name is not None
    return ReviewScope.storeOne(
        await queries.query(critic, name=name).makeOne(
            ReviewScope, api.reviewscope.InvalidName(value=name)
        )
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    filter: Optional[
        Union[api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter]
    ],
) -> Sequence[PublicType]:
    joins = []
    conditions = []
    if filter is not None:
        if isinstance(filter, api.repositoryfilter.RepositoryFilter):
            joins.append(join(repositoryfilterscopes=["scope=reviewscopes.id"]))
        else:
            joins.append(join(reviewfilterscopes=["scope=reviewscopes.id"]))
        conditions.append("filter={filter}")
    return ReviewScope.store(
        await queries.query(
            critic, queries.formatQuery(*conditions, joins=joins), filter=filter
        ).make(ReviewScope)
    )
