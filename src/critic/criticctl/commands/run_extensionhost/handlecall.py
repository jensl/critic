from __future__ import annotations

import asyncio
import io
import logging
import os
import pickle
import struct
from typing import AsyncIterator, Iterator, List, Optional, Union, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import extensions
from critic import pubsub
from critic.background.extensionhost import (
    CallError,
    CallRequest,
    CallResponse,
    EndpointRole,
    SubscriptionRole,
)

from .extension import Extension


HEADER_FMT = "!I"


async def handle_call(
    request: pubsub.IncomingRequest,
) -> Union[CallResponse, CallError]:
    message: object = request.payload
    assert isinstance(message, CallRequest)

    extension = await Extension.ensure(message.version_id)

    if isinstance(message.role, EndpointRole):
        role_type = "endpoint"
        command = message.role.request
        for role in extension.manifest.endpoints:
            if role.name == message.role.name:
                break
        else:
            return CallError(
                f"No matching role found in extension manifest: {message.role!r}"
            )
    elif isinstance(message.role, SubscriptionRole):
        role_type = "subscription"
        command = message.role.message
        for role in extension.manifest.subscriptions:
            if role.channel == message.role.message.channel:
                break
        else:
            return CallError(
                f"No matching role found in extension manifest: {message.role!r}"
            )
    else:
        return CallError(f"Role type not handled: {message.role!r}")

    package = extension.manifest.package
    assert package.package_type == "python"

    for entrypoint in package.entrypoints:
        if entrypoint.name == role.entrypoint:
            break
    else:
        return CallError(
            f"No matching entrypoint found in extension manifest: {role.entrypoint!r}"
        )

    async with extension.ensure_process(role_type, entrypoint) as process:
        response_items = []

        try:
            async for response in process.handle(
                message.user_id, message.accesstoken_id, command
            ):
                logger.debug("%s: response=%r", extension.extension_name, response)
                response_items.append(response)
        except Exception:
            logger.exception("call failed")
            success = False
        else:
            success = True

    # if stdout_data.getvalue():
    #     logger.debug("%s: stdout=%s", executable, stdout_data.getvalue().decode())
    # if stderr_data.getvalue():
    #     logger.debug("%s: stderr=%s", executable, stderr_data.getvalue().decode())

    return CallResponse(success=success, items=response_items)
