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
from typing import Any, Optional, Tuple, Sequence, Dict, Union

logger = logging.getLogger(__name__)

from . import Insert, Update, LazyAPIObject, Transaction, Modifier, protocol
from critic import api
from critic import base

PayloadArgs = Tuple[str, str, str, Any]


class CreatedSystemEvent(
    LazyAPIObject[api.systemevent.SystemEvent], api_module=api.systemevent
):
    def __init__(self, transaction: Transaction, payload_args: PayloadArgs):
        super().__init__(transaction)
        self.payload_args = payload_args

    async def create_payload(
        self, resource_name: str, subject: api.systemevent.SystemEvent, /
    ) -> protocol.CreatedSystemEvent:
        return protocol.CreatedSystemEvent(
            resource_name, subject.id, *self.payload_args
        )


def create_system_event(
    transaction: Transaction, category: str, key: str, title: str, data: Any
) -> CreatedSystemEvent:
    return CreatedSystemEvent(transaction, (category, key, title, data)).insert(
        category=category, key=key, title=title, data=json.dumps(data)
    )


class ModifySystemEvent(Modifier[api.systemevent.SystemEvent, CreatedSystemEvent]):
    def markAsHandled(self) -> None:
        self.transaction.items.append(Update(self.real).set(handled=True))

    @staticmethod
    def create(
        transaction: Transaction, category: str, key: str, title: str, data: Any
    ) -> ModifySystemEvent:
        return ModifySystemEvent(
            transaction, create_system_event(transaction, category, key, title, data)
        )
