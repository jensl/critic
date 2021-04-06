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

import logging
from typing import Callable, Tuple, Sequence

from critic.api.impl.queryhelper import QueryHelper, QueryResult, join

logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewping as public
from .apiobject import APIObjectImplWithId

PublicType = public.ReviewPing
ArgumentsType = Tuple[int, str]


class ReviewPing(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__message) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def event(self) -> api.reviewevent.ReviewEvent:
        return await api.reviewevent.fetch(self.critic, self.__id)

    @property
    def message(self) -> str:
        return self.__message

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "event", "message", default_order_by=["event ASC"]
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, event: api.reviewevent.ReviewEvent
) -> PublicType:
    if event.type != "pinged":
        raise api.reviewping.InvalidReviewEvent(event)
    return await ReviewPing.ensureOne(event.id, queries.idFetcher(critic, ReviewPing))


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, review: api.review.Review
) -> Sequence[PublicType]:
    return ReviewPing.store(
        await queries.query(
            critic,
            queries.formatQuery(
                "review={review}", joins=[join(reviewevents=["id=event"])]
            ),
            review=review,
        ).make(ReviewPing)
    )
