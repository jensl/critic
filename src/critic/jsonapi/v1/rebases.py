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

from typing import Sequence

from critic import api
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class Rebases(ResourceClass[api.rebase.Rebase], api_module=api.rebase):
    """The review rebases in this system."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(parameters: Parameters, value: api.rebase.Rebase) -> JSONResult:
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

        data: JSONResult = {
            "id": value.id,
            "review": value.review,
            "creator": value.creator,
            "branchupdate": value.branchupdate,
        }

        if isinstance(value, api.rebase.HistoryRewrite):
            data.update({"type": "history-rewrite"})
        else:
            assert isinstance(value, api.rebase.MoveRebase)
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

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.rebase.Rebase:
        """Retrieve one (or more) rebases in this system.

        REBASE_ID : integer

        Retrieve a rebase identified by its unique numeric id."""

        return await api.rebase.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.rebase.Rebase]:
        """Retrieve all rebases of a particular review.

        review : REVIEW_ID : -

        The review whose rebases to retrieve, identified by the review's
        unique numeric id."""

        review = await parameters.deduce(api.review.Review)
        return await api.rebase.fetchAll(parameters.critic, review=review)

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.rebase.Rebase:
        critic = parameters.critic

        converted = await convert(
            parameters, {"new_upstream?": str, "history_rewrite?": bool}, data
        )

        new_upstream = converted.get("new_upstream")
        history_rewrite = converted.get("history_rewrite")

        if (new_upstream is None) == (history_rewrite is None):
            raise UsageError(
                "Exactly one of the arguments new_upstream and history_rewrite "
                "must be specified."
            )

        if history_rewrite not in (None, True):
            raise UsageError("history_rewrite must be true, or omitted.")

        review = await parameters.deduce(api.review.Review)

        if review is None:
            raise UsageError("review must be specified when preparing a rebase")

        async with api.transaction.start(critic) as transaction:
            review_modifier = transaction.modifyReview(review)
            if new_upstream is not None:
                modifier = await review_modifier.prepareRebase(
                    new_upstream=new_upstream
                )
            else:
                modifier = await review_modifier.prepareRebase(history_rewrite=True)

            rebase = modifier.subject

        return rebase

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.rebase.Rebase]
    ) -> None:
        critic = parameters.critic

        if not values.is_single:
            raise UsageError("Only one rebase can currently be deleted per request")

        rebase = values.get()

        async with api.transaction.start(critic) as transaction:
            await transaction.modifyReview(await rebase.review).modifyRebase(
                rebase
            ).cancel()

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.rebase.Rebase:
        return await api.rebase.fetch(parameters.critic, numeric_id(value))

    @classmethod
    async def setAsContext(
        cls, parameters: Parameters, rebase: api.rebase.Rebase, /
    ) -> None:
        await super().setAsContext(parameters, rebase)
        # Also set the rebase's review (and repository and branch) as context.
        await Reviews.setAsContext(parameters, await rebase.review)


from .reviews import Reviews
