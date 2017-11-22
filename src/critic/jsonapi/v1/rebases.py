# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from typing import Sequence, Optional, Union

from critic import api
from critic import jsonapi


class Rebases(jsonapi.ResourceClass[api.log.rebase.Rebase], api_module=api.log.rebase):
    """The review rebases in this system."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.log.rebase.Rebase
    ) -> jsonapi.JSONResult:
        """{
             "id": integer,
             "review": integer,
             "creator": integer,
             "type": "history-rewrite" or "move",
             "branchupdate": integer,
             // if |type| is "move":
             "old_upstream": integer,
             "new_upstream": integer,
             "equivalent_merge": integer or null,
             "replayed_rebase": integer or null,
           }"""

        data: jsonapi.JSONResult = {
            "id": value.id,
            "review": value.review,
            "creator": value.creator,
            "branchupdate": value.branchupdate,
        }

        if isinstance(value, api.log.rebase.HistoryRewrite):
            data.update({"type": "history-rewrite"})
        else:
            assert isinstance(value, api.log.rebase.MoveRebase)
            data.update(
                {
                    "type": "move",
                    "old_upstream": value.old_upstream,
                    "new_upstream": value.new_upstream,
                    "equivalent_merge": value.equivalent_merge,
                    "replayed_rebase": value.replayed_rebase,
                }
            )

        return data

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.log.rebase.Rebase:
        """Retrieve one (or more) rebases in this system.

           REBASE_ID : integer

           Retrieve a rebase identified by its unique numeric id."""

        return await api.log.rebase.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.log.rebase.Rebase]:
        """Retrieve all rebases of a particular review.

           review : REVIEW_ID : -

           The review whose rebases to retrieve, identified by the review's
           unique numeric id."""

        review = await Reviews.deduce(parameters)
        return await api.log.rebase.fetchAll(parameters.critic, review=review)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.log.rebase.Rebase:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters, {"new_upstream?": str, "history_rewrite?": bool}, data
        )

        new_upstream = converted.get("new_upstream")
        history_rewrite = converted.get("history_rewrite")

        if (new_upstream is None) == (history_rewrite is None):
            raise jsonapi.UsageError(
                "Exactly one of the arguments new_upstream and history_rewrite "
                "must be specified."
            )

        if history_rewrite not in (None, True):
            raise jsonapi.UsageError("history_rewrite must be true, or omitted.")

        review = await Reviews.deduce(parameters)

        if review is None:
            raise jsonapi.UsageError("review must be specified when preparing a rebase")

        async with api.transaction.start(critic) as transaction:
            review_modifier = transaction.modifyReview(review)
            if new_upstream is not None:
                modifier = await review_modifier.prepareRebase(
                    new_upstream=new_upstream
                )
            else:
                modifier = await review_modifier.prepareRebase(history_rewrite=True)

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.log.rebase.Rebase]
    ) -> None:
        critic = parameters.critic

        if not isinstance(values, jsonapi.SingleValue):
            raise jsonapi.UsageError(
                "Only one rebase can currently be deleted per request"
            )

        rebase = values.get()

        async with api.transaction.start(critic) as transaction:
            transaction.modifyReview(rebase.review).modifyRebase(rebase).cancel()

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.log.rebase.Rebase:
        return await api.log.rebase.fetch(parameters.critic, jsonapi.numeric_id(value))

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, rebase: api.log.rebase.Rebase
    ) -> None:
        parameters.setContext(Rebases.name, rebase)
        # Also set the rebase's review (and repository and branch) as context.
        await Reviews.setAsContext(parameters, await rebase.review)


from .reviews import Reviews
