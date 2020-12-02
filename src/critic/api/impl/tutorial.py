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

from typing import Tuple

from critic import api
from critic.api import tutorial as public
from critic import dbaccess
from critic import tutorials
from . import apiobject


WrapperType = api.tutorial.Tutorial
ArgumentsType = Tuple[str, str]


class Tutorial(apiobject.APIObject[WrapperType, ArgumentsType, str]):
    wrapper_class = WrapperType

    def __init__(self, args: ArgumentsType):
        self.id, self.source = args


@public.fetchImpl
@Tutorial.cached
async def fetch(critic: api.critic.Critic, tutorial_id: str) -> WrapperType:
    try:
        source = tutorials.load(tutorial_id)
    except ValueError:
        raise dbaccess.ZeroRowsInResult
    return await Tutorial.makeOne(critic, values=(tutorial_id, source))
