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
from typing import Sequence, Union

logger = logging.getLogger(__name__)

from critic import api
from ..check import TypeCheckerContext, StringChecker, convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInputItem, JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class ReviewFilters(
    ResourceClass[api.reviewfilter.ReviewFilter], api_module=api.reviewfilter
):
    """Filters that apply to changes in a single review."""

    contexts = (None, "users", "reviews")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.reviewfilter.ReviewFilter
    ) -> JSONResult:
        """Filter {
          "id": integer, // the filter's id
          "subject": integer, // the filter's subject (affected user)
          "review": integer, // the filter's review's id
          "type": string, // "reviewer", "watcher" or "ignored"
          "path": string, // the filtered path
          "creator": integer, // the user who created the filter
        }"""

        return {
            "id": value.id,
            "subject": value.subject,
            "review": value.review,
            "type": value.type,
            "path": value.path,
            "default_scope": value.default_scope,
            "scopes": value.scopes,
            "creator": value.creator,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.reviewfilter.ReviewFilter:
        """Retrieve one (or more) of a user's repository filters.

        FILTER_ID : integer

        Retrieve a filter identified by the filters's unique numeric id."""

        filter = await api.reviewfilter.fetch(parameters.critic, numeric_id(argument))

        user = await parameters.deduce(api.user.User)
        if user and user != filter.subject:
            raise PathError("Filter does not belong to specified user")

        review = await parameters.deduce(api.review.Review)
        if review and review != filter.review:
            raise PathError("Filter does not belong to specified review")

        return filter

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.reviewfilter.ReviewFilter]:
        """All review filters.

        review : REVIEW_ID : -

        Include only filters that apply to the changes in the specified
        review.

        user : USER : -

        Include only filters whose subject is the specified user."""

        review = await parameters.deduce(api.review.Review)
        subject = await parameters.deduce(api.user.User)

        return await api.reviewfilter.fetchAll(
            parameters.critic, review=review, subject=subject
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> Union[api.reviewfilter.ReviewFilter, Sequence[api.reviewfilter.ReviewFilter]]:
        from critic import reviewing

        class FilterPath(StringChecker):
            async def check(
                self,
                context: TypeCheckerContext,
                value: JSONInputItem,
            ) -> str:
                path = reviewing.filters.sanitizePath(
                    await super().check(context, value)
                )
                try:
                    reviewing.filters.validatePattern(path)
                except reviewing.filters.PatternError as error:
                    return str(error)
                return path

        critic = parameters.critic

        one_converted, many_converted = await convert(
            parameters,
            {
                "subject?": api.user.User,
                "type": {"reviewer", "watcher", "ignored"},
                "path": FilterPath,
                "review?": api.review.Review,
                "default_scope?": bool,
                "scopes?": [api.reviewscope.ReviewScope],
            },
            data,
            "reviewfilters",
        )

        all_converted = [one_converted] if one_converted else many_converted
        assert all_converted is not None

        deduced_subject = await parameters.deduce(api.user.User)
        deduced_review = await parameters.deduce(api.review.Review)

        reviews = set(
            converted.get("review", deduced_review) for converted in all_converted
        )
        reviews.discard(None)

        if not reviews:
            raise UsageError("No review specified")
        if len(reviews) > 1:
            raise UsageError("Multiple reviews modified in one request")

        (review,) = reviews

        for converted in all_converted:
            if "subject" in converted:
                if deduced_subject and deduced_subject != converted["subject"]:
                    raise UsageError("Ambiguous request: multiple users specified")

        if not deduced_subject:
            deduced_subject = critic.effective_user

        created_filters = []

        async with api.transaction.start(critic) as transaction:
            review_modifier = transaction.modifyReview(review)

            for converted in all_converted:
                created_filters.append(
                    (
                        await review_modifier.createFilter(
                            converted.get("subject", deduced_subject),
                            converted["type"],
                            converted["path"],
                            converted.get("default_scope", True),
                            converted.get("scopes", []),
                        )
                    ).subject
                )

        if one_converted:
            return created_filters[0]

        return created_filters

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[api.reviewfilter.ReviewFilter],
    ) -> None:
        reviews = set()
        for filter in values:
            reviews.add(await filter.review)

        if len(reviews) > 1:
            raise UsageError("Multiple reviews modified in one request")

        review = reviews.pop()

        async with api.transaction.start(parameters.critic) as transaction:
            modifier = transaction.modifyReview(review)

            for filter in values:
                await (await modifier.modifyFilter(filter)).delete()
