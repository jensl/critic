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

ReviewIntegrationRequest = api.reviewintegrationrequest.ReviewIntegrationRequest


class ReviewIntegrationRequests(
    ResourceClass[ReviewIntegrationRequest],
    api_module=api.reviewintegrationrequest,
):
    contexts = (None, "reviews", "branches")

    @staticmethod
    async def json(
        parameters: Parameters, value: ReviewIntegrationRequest
    ) -> JSONResult:
        return {
            "id": value.id,
            "review": value.review,
            "target_branch": value.target_branch,
            "branchupdate": value.branchupdate,
            "squash": {
                "requested": value.squash_requested,
                "message": value.squash_message,
                "performed": value.squash_performed,
            },
            "autosquash": {
                "requested": value.autosquash_requested,
                "performed": value.autosquash_performed,
            },
            "integration": {
                "requested": value.integration_requested,
                "performed": value.integration_performed,
                "strategy_used": value.strategy_used,
            },
            "successful": value.successful,
            "error_message": value.error_message,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> ReviewIntegrationRequest:
        return await api.reviewintegrationrequest.fetch(
            parameters.critic, numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[ReviewIntegrationRequest]:
        review = await parameters.deduce(api.review.Review)
        target_branch = await parameters.deduce(api.branch.Branch)

        return await api.reviewintegrationrequest.fetchAll(
            parameters.critic, review=review, target_branch=target_branch
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> ReviewIntegrationRequest:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "review?": api.review.Review,
                "squash?": {"requested": bool, "message?": str},
                "autosquash?": {"requested": bool},
                "integration?": {"requested": bool},
            },
            data,
        )

        review = await parameters.deduce(api.review.Review)

        if not review:
            if "review" not in converted:
                raise UsageError.missingParameter("review")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise UsageError("Conflicting reviews specified")

        assert review

        do_squash = converted.get("squash", {}).get("requested", False)
        squash_message = converted.get("squash", {}).get("message")
        do_autosquash = converted.get("autosquash", {}).get("requested", False)
        do_integrate = converted.get("integration", {}).get("requested", True)

        async with api.transaction.start(critic) as transaction:
            return await (
                transaction.modifyReview(review).requestIntegration(
                    do_squash, squash_message, do_autosquash, do_integrate
                )
            )
