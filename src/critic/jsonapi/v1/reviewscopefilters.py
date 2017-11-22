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

from typing import Sequence, Optional, Union

from critic import api
from critic import jsonapi

ReviewScopeFilter = api.reviewscopefilter.ReviewScopeFilter


class ReviewScopeFilters(
    jsonapi.ResourceClass[ReviewScopeFilter], api_module=api.reviewscopefilter
):
    """Review scope filters."""

    contexts = (None, "repositories", "reviewscopes")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: ReviewScopeFilter
    ) -> jsonapi.JSONResult:
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

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> ReviewScopeFilter:
        return await api.reviewscopefilter.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[ReviewScopeFilter, Sequence[ReviewScopeFilter]]:
        return await api.reviewscopefilter.fetchAll(
            parameters.critic, repository=await Repositories.deduce(parameters)
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> ReviewScopeFilter:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {
                "repository?": api.repository.Repository,
                "scope?": api.reviewscope.ReviewScope,
                "path": str,
                "included": bool,
            },
            data,
        )

        repository = await Repositories.deduce(parameters)

        if not repository:
            if "repository" not in converted:
                raise jsonapi.UsageError.missingInput("repository")
            repository = converted["repository"]
        elif converted.get("repository", repository) != repository:
            raise jsonapi.UsageError("Conflicting repositories specified")
        assert repository

        scope = await ReviewScopes.deduce(parameters)

        if not scope:
            if "scope" not in converted:
                raise jsonapi.UsageError.missingInput("scope")
            scope = converted["scope"]
        elif converted.get("scope", scope) != scope:
            raise jsonapi.UsageError("Conflicting review scopes specified")
        assert scope

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.createReviewScopeFilter(
                repository, scope, converted["path"], converted["included"]
            )

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[ReviewScopeFilter],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for scope_filter in values:
                transaction.modifyReviewScopeFilter(scope_filter).delete()


from .repositories import Repositories
from .reviewscopes import ReviewScopes
