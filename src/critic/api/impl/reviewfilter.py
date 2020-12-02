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

from typing import Collection, Tuple, Sequence, Optional

from critic import api
from critic.api import reviewfilter as public
from . import apiobject


WrapperType = api.reviewfilter.ReviewFilter
ArgumentsType = Tuple[int, int, api.reviewfilter.FilterType, str, bool, int, int]


class ReviewFilter(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.reviewfilter.ReviewFilter
    column_names = ["id", "uid", "type", "path", "default_scope", "review", "creator"]

    __scopes: Optional[Collection[api.reviewscope.ReviewScope]]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__subject_id,
            self.type,
            self.path,
            self.default_scope,
            self.__review_id,
            self.__creator_id,
        ) = args
        self.__scopes = None

    async def getSubject(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__subject_id)

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.__review_id)

    async def getScopes(
        self, wrapper: WrapperType
    ) -> Collection[api.reviewscope.ReviewScope]:
        if self.__scopes is None:
            self.__scopes = await api.reviewscope.fetchAll(
                wrapper.critic, filter=wrapper
            )
        return self.__scopes

    async def getCreator(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__creator_id)


@public.fetchImpl
@ReviewFilter.cached
async def fetch(critic: api.critic.Critic, filter_id: int) -> WrapperType:
    async with ReviewFilter.query(
        critic, ["id={filter_id}"], filter_id=filter_id
    ) as result:
        return await ReviewFilter.makeOne(critic, result)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    subject: Optional[api.user.User],
) -> Sequence[WrapperType]:
    conditions = []
    if review:
        conditions.append("review={review}")
    if subject:
        conditions.append("uid={subject}")
    async with ReviewFilter.query(
        critic, conditions, review=review, subject=subject
    ) as result:
        return await ReviewFilter.make(critic, result)
