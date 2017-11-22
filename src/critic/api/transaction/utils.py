# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import functools
from typing import TypeVar, Callable, Any, cast

from critic import api

Function = TypeVar("Function", bound=Callable[..., Any])


def requireAdministrator(fn: Function) -> Function:
    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        transaction = getattr(self, "transaction", self)
        critic = cast(api.critic.Critic, getattr(transaction, "critic", transaction))
        api.PermissionDenied.raiseUnlessAdministrator(critic)
        return fn(self, *args, **kwargs)

    return cast(Function, wrapper)


def requireSystem(fn: Function) -> Function:
    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        transaction = getattr(self, "transaction", self)
        critic = getattr(transaction, "critic", transaction)
        api.PermissionDenied.raiseUnlessSystem(critic)
        return fn(self, *args, **kwargs)

    return cast(Function, wrapper)
