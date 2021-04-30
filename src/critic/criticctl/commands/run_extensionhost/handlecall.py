from __future__ import annotations

import logging
from typing import List, Sequence, Union, cast

logger = logging.getLogger(__name__)

from critic import api
from critic.base import binarylog
from critic import pubsub
from critic.protocol.extensionhost import (
    CallError,
    CallLogRecord,
    CallRequest,
    CallResponse,
    CallResponseItem,
    EndpointRole,
    ResponseItem,
    SubscriptionRole,
    EndpointRequest,
    SubscriptionMessage,
)

from .extension import Extension


HEADER_FMT = "!I"


async def handle_call_inner(
    request: CallRequest,
) -> Union[CallResponse, CallError]:
    extension = await Extension.ensure(request.version_id)
    command: Union[EndpointRequest, SubscriptionMessage]
    role: api.extensionversion.ExtensionVersion.Role

    if isinstance(request.role, EndpointRole):
        role_type = "endpoint"
        command = request.role.request
        for role in extension.manifest.endpoints:
            if role.name == request.role.name:
                break
        else:
            return CallError(
                f"No matching role found in extension manifest: {request.role!r}"
            )
    elif isinstance(request.role, SubscriptionRole):  # type: ignore
        role_type = "subscription"
        command = request.role.message
        for role in extension.manifest.subscriptions:
            if role.channel == request.role.message.channel:
                break
        else:
            return CallError(
                f"No matching role found in extension manifest: {request.role!r}"
            )
    else:
        return CallError(f"Role type not handled: {request.role!r}")

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
        success = True
        log_records: List[binarylog.BinaryLogRecord] = []

        def log_capture(record: binarylog.BinaryLogRecord) -> None:
            log_records.append(record)

        def format_log() -> Sequence[CallLogRecord]:
            return [
                CallLogRecord(record["level"], record["name"], record["message"])
                for record in log_records
            ]

        try:
            async for response in process.handle(
                request.user_id, request.accesstoken_id, command, log_capture
            ):
                logger.debug("%s: response=%r", extension.extension_name, response)
                if isinstance(response, ResponseItem) and response.error:
                    success = False
                elif isinstance(response, CallError):
                    success = False
                response_items.append(response)
        except Exception as error:
            return CallResponse(
                success=False, items=[CallError.from_exception(error)], log=format_log()
            )

    # if stdout_data.getvalue():
    #     logger.debug("%s: stdout=%s", executable, stdout_data.getvalue().decode())
    # if stderr_data.getvalue():
    #     logger.debug("%s: stderr=%s", executable, stderr_data.getvalue().decode())

    return CallResponse(success=success, items=response_items, log=format_log())


async def handle_call(
    request: pubsub.IncomingRequest,
) -> Union[CallResponse, CallError]:
    logger.debug(f"handle_call: {request=}")
    message = cast(object, request.payload)
    assert isinstance(message, CallRequest)

    async with api.critic.startSession(for_system=True) as critic:
        version = await api.extensionversion.fetch(critic, message.version_id)

        async with api.transaction.start(critic) as transaction:
            version_modifier = await transaction.modifyExtensionVersion(version)
            call_modifier = await version_modifier.recordCallRequest(message)
            call_id = call_modifier.subject.id

    response = await handle_call_inner(message)

    async with api.critic.startSession(for_system=True) as critic:
        version = await api.extensionversion.fetch(critic, message.version_id)
        call = await api.extensioncall.fetch(critic, call_id)

        async with api.transaction.start(critic) as transaction:
            version_modifier = await transaction.modifyExtensionVersion(version)
            call_modifier = await version_modifier.modifyExtensionCall(call)
            await call_modifier.recordResponse(response)

    return response
