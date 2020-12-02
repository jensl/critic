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

from .createapiobject import CreateAPIObject
from .item import Update
from .base import TransactionBase
from .modifier import Modifier
from .protocol import CreatedSystemEvent
from critic import api

PayloadArgs = Tuple[str, str, str, Any]


class CreateSystemEvent(
    CreateAPIObject[api.systemevent.SystemEvent], api_module=api.systemevent
):
    def __init__(self, transaction: TransactionBase, payload_args: PayloadArgs):
        super().__init__(transaction)
        self.payload_args = payload_args

    async def create_payload(
        self, resource_name: str, subject: api.systemevent.SystemEvent, /
    ) -> CreatedSystemEvent:
        return CreatedSystemEvent(resource_name, subject.id, *self.payload_args)

    @staticmethod
    async def make(
        transaction: TransactionBase, category: str, key: str, title: str, data: Any
    ) -> api.systemevent.SystemEvent:
        return await CreateSystemEvent(
            transaction, (category, key, title, data)
        ).insert(category=category, key=key, title=title, data=json.dumps(data))


class ModifySystemEvent(Modifier[api.systemevent.SystemEvent]):
    async def markAsHandled(self) -> None:
        await self.transaction.execute(Update(self.subject).set(handled=True))

    @staticmethod
    async def create(
        transaction: TransactionBase, category: str, key: str, title: str, data: Any
    ) -> ModifySystemEvent:
        return ModifySystemEvent(
            transaction,
            await CreateSystemEvent.make(transaction, category, key, title, data),
        )
