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
from typing import TypedDict

from critic import api
from ..resourceclass import ResourceClass
from ..parameters import Parameters


class JSONResult(TypedDict):
    name: str
    source: str


class Tutorials(ResourceClass[api.tutorial.Tutorial], api_module=api.tutorial):
    """Tutorial texts."""

    @staticmethod
    async def json(parameters: Parameters, value: api.tutorial.Tutorial) -> JSONResult:
        return JSONResult(name=value.name, source=value.source)

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.tutorial.Tutorial:
        return await api.tutorial.fetch(parameters.critic, argument)
