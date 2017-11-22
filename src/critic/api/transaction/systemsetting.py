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

from . import Update, LazyAPIObject, Transaction, Modifier, protocol
from .protocol import ModifiedSystemSetting
from critic import api

PayloadArgs = Tuple[str, str, str, Any]


class CreatedSystemSetting(
    LazyAPIObject[api.systemsetting.SystemSetting], api_module=api.systemsetting
):
    def __init__(self, transaction: Transaction, key: str):
        super().__init__(transaction)
        self.key = key

    async def create_payload(
        self, resource_name: str, subject: api.systemsetting.SystemSetting, /
    ) -> protocol.CreatedSystemSetting:
        return protocol.CreatedSystemSetting(resource_name, subject.id, self.key)


def create_system_setting(
    transaction: Transaction, key: str, description: str, value: Any, privileged: bool
) -> CreatedSystemSetting:
    transaction.addSystemEvent(
        "settings", key, "Setting created", {} if privileged else {"value": value},
    )
    return CreatedSystemSetting(transaction, key).insert(
        key=key, description=description, value=json.dumps(value), privileged=privileged
    )


class ModifySystemSetting(
    Modifier[api.systemsetting.SystemSetting, CreatedSystemSetting]
):
    def setValue(self, value: Any) -> None:
        if value == self.real.value:
            return
        self.modified = True
        if not self.real.is_privileged:
            self.updates["value"] = value
        self.transaction.addSystemEvent(
            "settings",
            self.real.key,
            "Value modified",
            {}
            if self.real.is_privileged
            else {"old_value": self.real.value, "new_value": value},
        )
        self.transaction.items.append(Update(self.real).set(value=json.dumps(value)))

    async def create_modified_payload(self) -> ModifiedSystemSetting:
        return ModifiedSystemSetting(
            self.resource_name, self.subject_id, self.updates, self.subject.key
        )

    @staticmethod
    def create(
        transaction: Transaction,
        key: str,
        description: str,
        value: Any,
        privileged: bool,
    ) -> ModifySystemSetting:
        return ModifySystemSetting(
            transaction,
            create_system_setting(transaction, key, description, value, privileged),
        )
