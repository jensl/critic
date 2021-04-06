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

import datetime
import logging
from typing import (
    Callable,
    Collection,
    Tuple,
    Optional,
    Sequence,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewevent as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = api.reviewevent.ReviewEvent
ArgumentsType = Tuple[int, int, int, api.reviewevent.EventType, datetime.datetime]


class ReviewEvent(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__review_id,
            self.__user_id,
            self.__type,
            self.__timestamp,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def type(self) -> api.reviewevent.EventType:
        return self.__type

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    def __str__(self) -> str:
        actor = "Critic" if self.__user_id is None else f"user {self.__user_id}"
        return "[event %d] r/%d: %r by %s" % (
            self.id,
            self.__review_id,
            self.type,
            actor,
        )

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def user(self) -> api.user.User:
        if self.__user_id is None:
            return api.user.system(self.critic)
        return await api.user.fetch(self.critic, self.__user_id)

    @property
    async def users(self) -> Collection[api.user.User]:
        async with api.critic.Query[int](
            self.critic,
            """
            SELECT uid
              FROM reviewusers
             WHERE review={review}
               AND event<={event}
            """,
            review=self.__review_id,
            event=self.id,
        ) as result:
            user_ids = await result.scalars()
        return await api.user.fetchMany(self.critic, user_ids)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "review", "uid", "type", "time"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    event_id: Optional[int],
    review: Optional[api.review.Review],
    event_type: Optional[public.EventType],
) -> ReviewEvent:
    if event_id is not None:
        return await ReviewEvent.ensureOne(
            event_id, queries.idFetcher(critic, ReviewEvent)
        )
    assert review and event_type
    return ReviewEvent.storeOne(
        await queries.query(critic, review=review, type=event_type).makeOne(
            ReviewEvent, public.NoSuchEvent(review, event_type)
        )
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, event_ids: Sequence[int]
) -> Sequence[ReviewEvent]:
    return await ReviewEvent.ensure(event_ids, queries.idsFetcher(critic, ReviewEvent))


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    user: Optional[api.user.User],
    event_type: Optional[api.reviewevent.EventType],
) -> Sequence[ReviewEvent]:
    return ReviewEvent.store(
        await queries.query(
            critic,
            review=review,
            uid=user,
            type=event_type,
        ).make(ReviewEvent)
    )
