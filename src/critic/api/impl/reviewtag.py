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

from typing import Callable, Collection, Tuple, Optional, Iterable, Sequence

from critic import api
from critic.api import reviewtag as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.ReviewTag
ArgumentsType = Tuple[int, str, str]


class ReviewTag(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__name, self.__description) = args
        return self.__id

    def getCacheKeys(self) -> Collection[object]:
        return (self.__id, self.__name)

    @property
    def id(self) -> int:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def description(self) -> str:
        return self.__description

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "name", "description"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, reviewtag_id: Optional[int], name: Optional[str]
) -> PublicType:
    if reviewtag_id is not None:
        return await ReviewTag.ensureOne(
            reviewtag_id, queries.idFetcher(critic, ReviewTag)
        )
    assert name is not None
    return await ReviewTag.ensureOne(
        name, queries.itemFetcher(critic, ReviewTag, "name")
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    reviewtag_ids: Optional[Iterable[int]],
    names: Optional[Iterable[str]] = None,
) -> Sequence[PublicType]:
    if reviewtag_ids is not None:
        return await ReviewTag.ensure(
            [*reviewtag_ids], queries.idsFetcher(critic, ReviewTag)
        )
    assert names is not None
    return await ReviewTag.ensure(
        [*names], queries.itemsFetcher(critic, ReviewTag, "name")
    )


@public.fetchAllImpl
async def fetchAll(critic: api.critic.Critic) -> Sequence[PublicType]:
    return ReviewTag.store(await queries.query(critic).make(ReviewTag))
