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

from datetime import datetime
import pickle

from critic import api, dbaccess, pubsub
from critic.protocol.extensionhost import CallRequest, CallResponse
from ..base import TransactionBase
from ..modifier import Modifier
from .create import CreateExtensionCall


class ModifyExtensionCall(Modifier[api.extensioncall.ExtensionCall]):
    async def recordResponse(self, response: CallResponse) -> None:
        async with self.update(successful=response.success) as update:
            update.set(
                response=pickle.dumps(response),
                successful=response.success,
                response_time=dbaccess.SQLExpression("NOW()"),
            )

    async def repeat(self) -> ModifyExtensionCall:
        extension = await self.subject.extension
        user = await self.subject.user

        installation = await api.extensioninstallation.fetch(
            self.critic, extension=extension, user=user
        )
        if installation is None:
            raise api.extensioncall.Error(
                f"Extension {await extension.key} no longer installed"
            )
        new_version = await installation.version

        old_request = self.subject.request
        new_request = CallRequest(
            new_version.id,
            old_request.user_id,
            old_request.accesstoken_id,
            old_request.role,
        )

        async with pubsub.connect("criticctl extension repeat-call") as client:
            request = await client.request(
                pubsub.Payload(new_request), pubsub.ChannelName("extension/call")
            )

            await request.delivery

            response = await request.response

        assert isinstance(response, CallResponse)

        return ModifyExtensionCall(
            self.transaction,
            await api.extensioncall.fetch(self.critic, new_request.request_id),
        )

    @staticmethod
    async def create(
        transaction: TransactionBase,
        version: api.extensionversion.ExtensionVersion,
        request: CallRequest,
    ) -> ModifyExtensionCall:
        return ModifyExtensionCall(
            transaction,
            await CreateExtensionCall.make(transaction, version, request),
        )
