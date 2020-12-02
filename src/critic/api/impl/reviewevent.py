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
from typing import Tuple, Optional, Sequence, Iterable

logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewevent as public
from . import apiobject

WrapperType = api.reviewevent.ReviewEvent
ArgumentsType = Tuple[int, int, int, api.reviewevent.EventType, datetime.datetime]


class ReviewEvent(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.reviewevent.ReviewEvent
    column_names = ["id", "review", "uid", "type", "time"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.__review_id, self.__user_id, self.type, self.timestamp) = args

    def __str__(self) -> str:
        actor = "Critic" if self.__user_id is None else f"user {self.__user_id}"
        return "[event %d] r/%d: %r by %s" % (
            self.id,
            self.__review_id,
            self.type,
            actor,
        )

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.__review_id)

    async def getUser(self, critic: api.critic.Critic) -> api.user.User:
        if self.__user_id is None:
            return api.user.system(critic)
        return await api.user.fetch(critic, self.__user_id)


@public.fetchImpl
@ReviewEvent.cached
async def fetch(critic: api.critic.Critic, event_id: int) -> WrapperType:
    async with ReviewEvent.query(
        critic, ["id={event_id}"], event_id=event_id
    ) as result:
        return await ReviewEvent.makeOne(critic, result)


@public.fetchManyImpl
@ReviewEvent.cachedMany
async def fetchMany(
    critic: api.critic.Critic, event_ids: Iterable[int]
) -> Sequence[WrapperType]:
    async with ReviewEvent.query(
        critic, ["id=ANY({event_ids})"], event_ids=list(event_ids)
    ) as result:
        return await ReviewEvent.make(critic, result)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    user: Optional[api.user.User],
    event_type: Optional[api.reviewevent.EventType],
) -> Sequence[WrapperType]:
    conditions = []
    if review:
        conditions.append("review={review}")
    if user:
        conditions.append("uid={user}")
    if event_type:
        conditions.append("type={event_type}")

    async with ReviewEvent.query(
        critic, conditions, review=review, user=user, event_type=event_type
    ) as result:
        return await ReviewEvent.make(critic, result)
