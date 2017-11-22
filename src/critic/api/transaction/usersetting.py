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

import json
import re
from typing import Any, Union

from . import Transaction, Update, Delete, Modifier
from .user import CreatedUser, CreatedUserObject

from critic import api


def valueAsJSON(value: Any) -> str:
    try:
        return json.dumps(value)
    except TypeError as error:
        raise api.usersetting.Error(f"Value is not JSON compatible: {error}")


def validate_usersetting(scope: str, name: str) -> None:
    if not (1 <= len(scope) <= 64):
        raise api.usersetting.InvalidScope(
            "Scope must be between 1 and 64 characters long"
        )
    if not re.match("^[A-Za-z0-9_]+$", scope):
        raise api.usersetting.InvalidScope(
            "Scope must contain only characters from the set [A-Za-z0-9_]"
        )

    if not (1 <= len(name) <= 256):
        raise api.usersetting.InvalidName(
            "Name must be between 1 and 256 characters long"
        )
    if not re.match(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$", name):
        raise api.usersetting.InvalidName(
            "Name must consist of '.'-separated tokens containing only "
            "characters from the set [A-Za-z0-9_]"
        )


class CreatedUserSetting(CreatedUserObject, api_module=api.usersetting):
    @staticmethod
    async def make(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        scope: str,
        name: str,
        value: Any,
    ) -> CreatedUserSetting:
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

        return CreatedUserSetting(transaction, user).insert(
            uid=user, scope=scope, name=name, value=valueAsJSON(value)
        )


class ModifyUserSetting(Modifier[api.usersetting.UserSetting, CreatedUserSetting]):
    def setValue(self, value: Any) -> None:
        self.transaction.items.append(
            Update(self.subject).set(value=valueAsJSON(value))
        )

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    async def create(
        transaction: Transaction,
        user: Union[api.user.User, CreatedUser],
        scope: str,
        name: str,
        value: Any,
    ) -> ModifyUserSetting:
        return ModifyUserSetting(
            transaction,
            await CreatedUserSetting.make(transaction, user, scope, name, value),
        )
