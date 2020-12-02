# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from typing import Sequence, Union

from critic import api
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values

ReviewScopeFilter = api.reviewscopefilter.ReviewScopeFilter


class ReviewScopeFilters(
    ResourceClass[ReviewScopeFilter], api_module=api.reviewscopefilter
):
    """Review scope filters."""

    contexts = (None, "repositories", "reviewscopes")

    @staticmethod
    async def json(parameters: Parameters, value: ReviewScopeFilter) -> JSONResult:
        """ReviewScopeFilter {
          "id": integer, // the filter's unique id
          "repository": integer,
          "scope": integer,
          "path": string, // the filter's path
        }"""

        return {
            "id": value.id,
            "repository": value.repository,
            "scope": value.scope,
            "path": value.path,
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> ReviewScopeFilter:
        return await api.reviewscopefilter.fetch(
            parameters.critic, numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[ReviewScopeFilter, Sequence[ReviewScopeFilter]]:
        return await api.reviewscopefilter.fetchAll(
            parameters.critic,
            repository=await parameters.deduce(api.repository.Repository),
        )

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> ReviewScopeFilter:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "repository?": api.repository.Repository,
                "scope?": api.reviewscope.ReviewScope,
                "path": str,
                "included": bool,
            },
            data,
        )

        repository = await parameters.deduce(api.repository.Repository)

        if not repository:
            if "repository" not in converted:
                raise UsageError.missingInput("repository")
            repository = converted["repository"]
        elif converted.get("repository", repository) != repository:
            raise UsageError("Conflicting repositories specified")
        assert repository

        scope = await parameters.deduce(api.reviewscope.ReviewScope)

        if not scope:
            if "scope" not in converted:
                raise UsageError.missingInput("scope")
            scope = converted["scope"]
        elif converted.get("scope", scope) != scope:
            raise UsageError("Conflicting review scopes specified")
        assert scope

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.createReviewScopeFilter(
                    repository, scope, converted["path"], converted["included"]
                )
            ).subject

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[ReviewScopeFilter],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for scope_filter in values:
                await transaction.modifyReviewScopeFilter(scope_filter).delete()
