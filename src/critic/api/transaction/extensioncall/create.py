# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

import logging
import pickle

from critic.protocol.extensionhost import CallRequest

logger = logging.getLogger(__name__)

from critic import api
from ..createapiobject import CreateAPIObject
from ..base import TransactionBase


class CreateExtensionCall(
    CreateAPIObject[api.extensioncall.ExtensionCall],
    api_module=api.extensioncall,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        version: api.extensionversion.ExtensionVersion,
        request: CallRequest,
    ) -> api.extensioncall.ExtensionCall:
        return await CreateExtensionCall(transaction).insert(
            id=request.request_id,
            version=version,
            uid=request.user_id if isinstance(request.user_id, int) else None,
            accesstoken=request.accesstoken_id,
            request=pickle.dumps(request),
        )
