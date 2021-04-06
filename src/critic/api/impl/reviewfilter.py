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

from typing import Callable, Collection, Tuple, Sequence, Optional

from critic import api
from critic.api import reviewfilter as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult


PublicType = public.ReviewFilter
ArgumentsType = Tuple[int, int, api.reviewfilter.FilterType, str, bool, int, int]


class ReviewFilter(PublicType, APIObjectImplWithId, module=public):
    __scopes: Optional[Collection[api.reviewscope.ReviewScope]]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__subject_id,
            self.__type,
            self.__path,
            self.__default_scope,
            self.__review_id,
            self.__creator_id,
        ) = args
        self.__scopes = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def subject(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__subject_id)

    @property
    def type(self) -> public.FilterType:
        return self.__type

    @property
    def path(self) -> str:
        return self.__path

    @property
    def default_scope(self) -> bool:
        return self.__default_scope

    @property
    async def scopes(self) -> Collection[api.reviewscope.ReviewScope]:
        if self.__scopes is None:
            self.__scopes = await api.reviewscope.fetchAll(self.critic, filter=self)
        return self.__scopes

    @property
    async def creator(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__creator_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "uid",
    "type",
    "path",
    "default_scope",
    "review",
    "creator",
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, filter_id: int) -> PublicType:
    return await ReviewFilter.ensureOne(
        filter_id, queries.idFetcher(critic, ReviewFilter)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    subject: Optional[api.user.User],
    scope: Optional[api.reviewscope.ReviewScope],
) -> Sequence[PublicType]:
    return ReviewFilter.store(
        await queries.query(critic, review=review, uid=subject, scope=scope).make(
            ReviewFilter
        )
    )
