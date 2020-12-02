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
from typing import Sequence

logger = logging.getLogger(__name__)

from critic import api
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import numeric_id
from .timestamp import timestamp


class ReviewEvents(
    ResourceClass[api.reviewevent.ReviewEvent], api_module=api.reviewevent
):
    """Events of reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.reviewevent.ReviewEvent
    ) -> JSONResult:
        return {
            "id": value.id,
            "review": value.review,
            "user": value.user,
            "type": value.type,
            "timestamp": timestamp(value.timestamp),
            "branchupdate": value.branchupdate,
            "batch": value.batch,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.reviewevent.ReviewEvent:
        return await api.reviewevent.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.reviewevent.ReviewEvent]:
        review = await parameters.deduce(api.review.Review)
        if review is None:
            raise UsageError("Missing required parameter 'review'")
        user = await parameters.deduce(api.user.User)
        event_type = parameters.query.get(
            "event_type", converter=api.reviewevent.as_event_type
        )
        return await api.reviewevent.fetchAll(
            parameters.critic, review=review, user=user, event_type=event_type
        )
