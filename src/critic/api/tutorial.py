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

from abc import abstractmethod
from typing import Awaitable, Callable
from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="tutorial"):
    """Base exception for all errors related to the Tutorial class"""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid tutorial name is used"""

    pass


class Tutorial(api.APIObject):
    """Representation of a tutorial text"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def source(self) -> str:
        ...


async def fetch(critic: api.critic.Critic, tutorial_id: str, /) -> Tutorial:
    return await fetchImpl.get()(critic, tutorial_id)


resource_name = "tutorials"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, str], Awaitable[Tutorial]]
] = FunctionRef()