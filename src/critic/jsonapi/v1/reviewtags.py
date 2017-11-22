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


class ReviewTags(
    jsonapi.ResourceClass[api.reviewtag.ReviewTag], api_module=api.reviewtag
):
    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.reviewtag.ReviewTag
    ) -> jsonapi.JSONResult:
        """ReviewTag {
             "id": integer,
             "name": string,
             "description": string,
           }"""

        return {
            "id": value.id,
            "name": value.name,
            "description": value.description,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.reviewtag.ReviewTag:
        return await api.reviewtag.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.reviewtag.ReviewTag]:
        return await api.reviewtag.fetchAll(parameters.critic)
