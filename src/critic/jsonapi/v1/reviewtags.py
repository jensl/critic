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
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import numeric_id


class ReviewTags(ResourceClass[api.reviewtag.ReviewTag], api_module=api.reviewtag):
    @staticmethod
    async def json(
        parameters: Parameters, value: api.reviewtag.ReviewTag
    ) -> JSONResult:
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

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.reviewtag.ReviewTag:
        return await api.reviewtag.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.reviewtag.ReviewTag]:
        return await api.reviewtag.fetchAll(parameters.critic)
