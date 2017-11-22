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
from typing import Tuple, Sequence

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api

WrapperType = api.reviewping.ReviewPing
ArgumentsType = Tuple[int, str]


class ReviewPing(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.reviewping.ReviewPing
    column_names = ["event", "message"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.message) = args

    @staticmethod
    def cacheKey(wrapper: WrapperType) -> int:
        return wrapper._impl.id

    @staticmethod
    def makeCacheKey(args: ArgumentsType) -> int:
        return args[0]

    async def getEvent(self, critic: api.critic.Critic) -> api.reviewevent.ReviewEvent:
        return await api.reviewevent.fetch(critic, self.id)


@ReviewPing.cached
async def fetch(
    critic: api.critic.Critic, event: api.reviewevent.ReviewEvent
) -> WrapperType:
    if event.type != "pinged":
        raise api.reviewping.InvalidReviewEvent(event)
    async with ReviewPing.query(critic, ["event={event}"], event=event) as result:
        return await ReviewPing.makeOne(critic, result)


async def fetchAll(
    critic: api.critic.Critic, review: api.review.Review
) -> Sequence[WrapperType]:
    async with ReviewPing.query(
        critic,
        f"""SELECT {ReviewPing.columns()}
              FROM {ReviewPing.table()}
              JOIN reviewevents ON (reviewevents.id=reviewpings.event)
             WHERE reviewevents.review={{review}}
          ORDER BY reviewpings.event""",
        review=review,
    ) as result:
        return await ReviewPing.make(critic, result)
