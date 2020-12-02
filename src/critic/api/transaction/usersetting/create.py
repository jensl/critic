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

from typing import Any

from critic import api
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from . import valueAsJSON


class CreatedUserSetting(
    CreateAPIObject[api.usersetting.UserSetting], api_module=api.usersetting
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        user: api.user.User,
        scope: str,
        name: str,
        value: Any,
    ) -> api.usersetting.UserSetting:
        critic = transaction.critic

        if user == critic.effective_user:
            try:
                await api.usersetting.fetch(critic, scope=scope, name=name)
            except api.usersetting.NotDefined:
                pass
            else:
                raise api.usersetting.Error(
                    "User setting already defined: %s:%s" % (scope, name)
                )

        return await CreatedUserSetting(transaction).insert(
            uid=user, scope=scope, name=name, value=valueAsJSON(value)
        )
