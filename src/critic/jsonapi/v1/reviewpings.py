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
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id


class ReviewPings(
    ResourceClass[api.reviewping.ReviewPing],
    api_module=api.reviewping,
    exceptions=(api.reviewping.Error, api.reviewevent.Error, api.review.Error),
):
    """Pings of reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.reviewping.ReviewPing
    ) -> JSONResult:
        return {"event": value.event, "message": value.message}

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.reviewping.ReviewPing:
        return await api.reviewping.fetch(
            parameters.critic,
            await api.reviewevent.fetch(parameters.critic, numeric_id(argument)),
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.reviewping.ReviewPing]:
        review = await parameters.deduce(api.review.Review)
        if review is None:
            raise UsageError.missingParameter("review")
        return await api.reviewping.fetchAll(parameters.critic, review)

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.reviewping.ReviewPing:
        critic = parameters.critic

        review = await parameters.deduce(api.review.Review)
        converted = await convert(
            parameters, {"review?": api.review.Review, "message?": str}, data
        )

        if not review:
            if "review" not in converted:
                raise UsageError.missingParameter("review")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise UsageError("Conflicting reviews specified")
        assert review

        async with api.transaction.start(critic) as transaction:
            return await transaction.modifyReview(review).pingReview(
                converted["message"]
            )
