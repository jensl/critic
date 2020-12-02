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
from ..item import Update, Delete
from ..modifier import Modifier
from . import valueAsJSON
from .create import CreatedUserSetting


class ModifyUserSetting(Modifier[api.usersetting.UserSetting]):
    async def setValue(self, value: Any) -> None:
        await self.transaction.execute(
            Update(self.subject).set(value=valueAsJSON(value))
        )

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        user: api.user.User,
        scope: str,
        name: str,
        value: Any,
    ) -> ModifyUserSetting:
        return ModifyUserSetting(
            transaction,
            await CreatedUserSetting.make(transaction, user, scope, name, value),
        )
