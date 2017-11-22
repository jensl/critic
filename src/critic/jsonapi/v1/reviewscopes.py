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


class ReviewScopes(
    jsonapi.ResourceClass[api.reviewscope.ReviewScope], api_module=api.reviewscope
):
    """Review scopes."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.reviewscope.ReviewScope
    ) -> jsonapi.JSONResult:
        """ReviewScope {
             "id": integer, // the scope's unique id
             "name": string, // the scope's name
           }"""

        return {"id": value.id, "name": value.name}

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.reviewscope.ReviewScope:
        return await api.reviewscope.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.reviewscope.ReviewScope, Sequence[api.reviewscope.ReviewScope]]:
        name = parameters.getQueryParameter("name")

        if name is not None:
            return await api.reviewscope.fetch(parameters.critic, name=name)

        return await api.reviewscope.fetchAll(parameters.critic)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.reviewscope.ReviewScope:
        critic = parameters.critic

        converted = await jsonapi.convert(parameters, {"name": str}, data,)

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.createReviewScope(converted["name"])

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.reviewscope.ReviewScope],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for scope in values:
                transaction.modifyReviewScope(scope).delete()

    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters,
    ) -> Optional[api.reviewscope.ReviewScope]:
        scope = parameters.context.get("reviewscopes")
        scope_parameter = parameters.getQueryParameter("scope")
        if scope_parameter is not None:
            if scope is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: scope=%s" % scope_parameter
                )
            scope = await ReviewScopes.fromParameterValue(parameters, scope_parameter)
        return scope

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.reviewscope.ReviewScope:
        scope_id, name = jsonapi.id_or_name(value)
        if scope_id is not None:
            return await api.reviewscope.fetch(parameters.critic, scope_id)
        else:
            assert name is not None
            return await api.reviewscope.fetch(parameters.critic, name=name)
