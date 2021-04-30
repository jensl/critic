# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Call 2.0 (the "License"); you may not
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

import email.message
import logging
from typing import Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.protocol.extensionhost import (
    CallRequest,
    CallResponse,
    EndpointRequest,
    EndpointRole,
    SubscriptionMessage,
    SubscriptionRole,
)

from ..check import convert
from ..exceptions import PathError, UsageError
from ..parameters import Parameters
from ..resourceclass import ResourceClass
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from .timestamp import timestamp

ExtensionCall = api.extensioncall.ExtensionCall


def endpoint_request(request: EndpointRequest) -> object:
    return {
        "method": request.method,
        "path": request.path,
        "query": {key: value for (key, value) in request.query},
    }


def subscription_payload(payload: object) -> object:
    payload_type = type(payload)
    result = {"__type__": f"{payload_type.__module__}.{payload_type.__qualname__}"}
    if isinstance(payload, email.message.EmailMessage):
        result["subject"] = payload["subject"]
        result["to"] = payload["to"]
        result["from"] = payload["from"]
        result["message_id"] = payload["message-id"]
    elif isinstance(payload, api.transaction.protocol.APIObjectBase):
        result.update(payload.serialize())
    return result


def subscription_message(message: SubscriptionMessage) -> object:
    return {
        "channel": message.channel,
        "payload": subscription_payload(message.payload),
    }


def request(request: CallRequest) -> object:
    if isinstance(request.role, EndpointRole):
        return {
            "type": "endpoint",
            "name": request.role.name,
            "request": endpoint_request(request.role.request),
        }
    elif isinstance(request.role, SubscriptionRole):
        return {
            "type": "subscription",
            "message": subscription_message(request.role.message),
        }
    return {}


def response(response: CallResponse) -> object:
    return {}


class ExtensionCalls(ResourceClass[ExtensionCall], api_module=api.extensioncall):
    """Extension versoins."""

    contexts = (None, "extensions")

    @staticmethod
    async def json(parameters: Parameters, value: ExtensionCall) -> JSONResult:
        logger.debug(f"{value.request_time=} {value.request_time.tzinfo=}")
        return {
            "id": value.id.to_bytes(8, "big", signed=True).hex(),
            "version": value.version,
            "user": value.user,
            "accesstoken": value.accesstoken,
            "request": request(value.request),
            "response": response(value.response) if value.response else None,
            "successful": value.successful,
            "request_time": timestamp(value.request_time),
            "response_time": timestamp(value.response_time),
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> ExtensionCall:
        """Retrieve one (or more) extension versions by id.

        CALL_ID : integer

        Retrieve an extension version identified by its unique numeric id."""

        if not api.critic.settings().extensions.enabled:
            raise PathError("Extension support not enabled", code="NO_EXTENSIONS")

        return await api.extensioncall.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[ExtensionCall]:
        """Retrieve all extension versions."""

        if not api.critic.settings().extensions.enabled:
            raise UsageError("Extension support not enabled", code="NO_EXTENSIONS")

        version = await parameters.deduce(api.extensionversion.ExtensionVersion)
        extension = await parameters.deduce(api.extension.Extension)

        if version:
            if extension:
                if extension != await version.extension:
                    raise UsageError("invalid extension and version combination")

            return await api.extensioncall.fetchAll(parameters.critic, version=version)

        if not extension:
            raise UsageError.missingParameter("extension")

        return await api.extensioncall.fetchAll(parameters.critic, extension=extension)

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.extensioncall.ExtensionCall:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {"repeat": api.extensioncall.ExtensionCall},
            data,
        )

        call = converted["repeat"]

        async with api.transaction.start(critic) as transaction:
            version_modifier = await transaction.modifyExtensionVersion(
                await call.version
            )
            call_modifier = await version_modifier.modifyExtensionCall(call)
            return (await call_modifier.repeat()).subject
