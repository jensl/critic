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

import json
import logging
from typing import Any, Tuple


logger = logging.getLogger(__name__)

from .item import Update
from .base import TransactionBase
from .modifier import Modifier
from .protocol import CreatedSystemSetting, ModifiedSystemSetting
from .createapiobject import CreateAPIObject
from .systemevent import CreateSystemEvent
from critic import api

PayloadArgs = Tuple[str, str, str, Any]


class CreateSystemSetting(
    CreateAPIObject[api.systemsetting.SystemSetting], api_module=api.systemsetting
):
    def __init__(self, transaction: TransactionBase, key: str):
        super().__init__(transaction)
        self.key = key

    async def create_payload(
        self, resource_name: str, subject: api.systemsetting.SystemSetting, /
    ) -> CreatedSystemSetting:
        return CreatedSystemSetting(resource_name, subject.id, self.key)

    @staticmethod
    async def make(
        transaction: TransactionBase,
        key: str,
        description: str,
        value: Any,
        privileged: bool,
    ) -> api.systemsetting.SystemSetting:
        await CreateSystemEvent.make(
            transaction,
            "settings",
            key,
            "Setting created",
            {} if privileged else {"value": value},
        )
        return await CreateSystemSetting(transaction, key).insert(
            key=key,
            description=description,
            value=json.dumps(value),
            privileged=privileged,
        )


class ModifySystemSetting(Modifier[api.systemsetting.SystemSetting]):
    async def setValue(self, value: Any) -> None:
        if value == self.subject.value:
            return
        self.modified = True
        if not self.subject.is_privileged:
            self.updates["value"] = value
        await CreateSystemEvent.make(
            self.transaction,
            "settings",
            self.subject.key,
            "Value modified",
            {}
            if self.subject.is_privileged
            else {"old_value": self.subject.value, "new_value": value},
        )
        await self.transaction.execute(
            Update(self.subject).set(value=json.dumps(value))
        )

    async def create_modified_payload(self, object_id:int) -> ModifiedSystemSetting:
        return ModifiedSystemSetting(
            self.resource_name, object_id, self.updates, self.subject.key
        )

    @staticmethod
    async def create(
        transaction: TransactionBase,
        key: str,
        description: str,
        value: Any,
        privileged: bool,
    ) -> ModifySystemSetting:
        return ModifySystemSetting(
            transaction,
            await CreateSystemSetting.make(
                transaction, key, description, value, privileged
            ),
        )
