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
from typing import Sequence, Optional, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class ReviewPings(
    jsonapi.ResourceClass[api.reviewping.ReviewPing],
    api_module=api.reviewping,
    exceptions=(api.reviewping.Error, api.reviewevent.Error, api.review.Error),
):
    """Pings of reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.reviewping.ReviewPing
    ) -> jsonapi.JSONResult:
        return {"event": value.event, "message": value.message}

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, value: str
    ) -> api.reviewping.ReviewPing:
        return await api.reviewping.fetch(
            parameters.critic,
            await api.reviewevent.fetch(parameters.critic, jsonapi.numeric_id(value)),
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.reviewping.ReviewPing]:
        review = await Reviews.deduce(parameters)
        if review is None:
            raise jsonapi.UsageError.missingParameter("review")
        return await api.reviewping.fetchAll(parameters.critic, review)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.reviewping.ReviewPing:
        critic = parameters.critic

        review = await Reviews.deduce(parameters)
        converted = await jsonapi.convert(
            parameters, {"review?": api.review.Review, "message?": str}, data
        )

        if not review:
            if "review" not in converted:
                raise jsonapi.UsageError.missingParameter("review")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise jsonapi.UsageError("Conflicting reviews specified")
        assert review

        async with api.transaction.start(critic) as transaction:
            created_ping = await transaction.modifyReview(review).pingReview(
                converted["message"]
            )

        return await created_ping


from .reviews import Reviews
