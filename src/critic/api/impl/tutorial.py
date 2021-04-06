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
from typing import Collection

from critic import api
from critic.api import tutorial as public
from critic.api.apiobject import Actual
from critic import dbaccess
from critic import tutorials
from .apiobject import APIObjectImpl


PublicType = public.Tutorial


class Tutorial(PublicType, APIObjectImpl, module=public):
    wrapper_class = PublicType

    def __init__(self, critic: api.critic.Critic, name: str, source: str):
        self.__name = name
        self.__source = source

    def getCacheKeys(self) -> Collection[str]:
        return (self.__name,)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def name(self) -> str:
        return self.__name

    @property
    def source(self) -> str:
        return self.__source


@public.fetchImpl
async def fetch(critic: api.critic.Critic, name: str) -> PublicType:
    async def make(name: str) -> Tutorial:
        try:
            source = tutorials.load(name)
        except ValueError:
            raise dbaccess.ZeroRowsInResult
        return Tutorial(critic, name, source)

    return await Tutorial.ensureOne(name, make)
