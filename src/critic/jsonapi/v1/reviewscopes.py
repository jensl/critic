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
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import id_or_name, numeric_id
from ..values import Values


class ReviewScopes(
    ResourceClass[api.reviewscope.ReviewScope], api_module=api.reviewscope
):
    """Review scopes."""

    @staticmethod
    async def json(
        parameters: Parameters, value: api.reviewscope.ReviewScope
    ) -> JSONResult:
        """ReviewScope {
          "id": integer, // the scope's unique id
          "name": string, // the scope's name
        }"""

        return {"id": value.id, "name": value.name}

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.reviewscope.ReviewScope:
        return await api.reviewscope.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.reviewscope.ReviewScope, Sequence[api.reviewscope.ReviewScope]]:
        name = parameters.query.get("name")

        if name is not None:
            return await api.reviewscope.fetch(parameters.critic, name=name)

        return await api.reviewscope.fetchAll(parameters.critic)

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.reviewscope.ReviewScope:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {"name": str},
            data,
        )

        async with api.transaction.start(critic) as transaction:
            return (await transaction.createReviewScope(converted["name"])).subject

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[api.reviewscope.ReviewScope],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for scope in values:
                await transaction.modifyReviewScope(scope).delete()

    @classmethod
    async def deduce(
        cls,
        parameters: Parameters,
    ) -> Optional[api.reviewscope.ReviewScope]:
        scope = parameters.in_context(api.reviewscope.ReviewScope)
        scope_parameter = parameters.query.get("scope")
        if scope_parameter is not None:
            if scope is not None:
                raise UsageError(
                    "Redundant query parameter: scope=%s" % scope_parameter
                )
            scope = await ReviewScopes.fromParameterValue(parameters, scope_parameter)
        return scope

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.reviewscope.ReviewScope:
        scope_id, name = id_or_name(value)
        if scope_id is not None:
            return await api.reviewscope.fetch(parameters.critic, scope_id)
        else:
            assert name is not None
            return await api.reviewscope.fetch(parameters.critic, name=name)
