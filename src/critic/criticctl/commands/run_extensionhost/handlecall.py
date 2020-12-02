from __future__ import annotations

import logging
from typing import List, Union, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub
from critic.background.extensionhost import (
    CallError,
    CallRequest,
    CallResponse,
    CallResponseItem,
    EndpointRole,
    SubscriptionRole,
    EndpointRequest,
    SubscriptionMessage,
)

from .extension import Extension


HEADER_FMT = "!I"


async def handle_call(
    request: pubsub.IncomingRequest,
) -> Union[CallResponse, CallError]:
    logger.debug(f"handle_call: {request=}")
    message = cast(object, request.payload)
    assert isinstance(message, CallRequest)

    extension = await Extension.ensure(message.version_id)
    command: Union[EndpointRequest, SubscriptionMessage]
    role: api.extensionversion.ExtensionVersion.Role

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
    elif isinstance(message.role, SubscriptionRole):  # type: ignore
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
        logger.debug(f"{process=}")

        response_items: List[CallResponseItem] = []

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
