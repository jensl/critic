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

import aiohttp
import aiohttp.web
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub
from critic.base import asyncutils

CODE_PROTOCOL_ERROR = 1002
CODE_INTERNAL_ERROR = 1012


class ProtocolError(Exception):
    pass


def serialize(payload: object, promiscuous: bool) -> Optional[Dict[str, Any]]:
    if isinstance(
        payload,
        (
            api.transaction.protocol.CreatedAPIObject,
            api.transaction.protocol.ModifiedAPIObject,
            api.transaction.protocol.DeletedAPIObject,
        ),
    ):
        return payload.serialize()
    if promiscuous and isinstance(payload, dict):
        return cast(Dict[str, Any], payload)
    return None


async def handle_published(
    ws: aiohttp.web.WebSocketResponse,
    channel_name: Union[pubsub.ChannelName, Tuple[pubsub.ChannelName, ...]],
    message: pubsub.Message,
    promiscuous: bool = False,
) -> None:
    logger.debug("published to %r: %r", channel_name, message)
    payload = serialize(message.payload, promiscuous)
    if payload is None:
        logger.debug(" - not serialized; skipping")
    await ws.send_str(
        json.dumps(
            {"publish": {"channel": channel_name, "message": payload}}, skipkeys=True
        )
    )


async def handle_incoming(
    ws: aiohttp.web.WebSocketResponse,
    pubsub_client: pubsub.Client,
    message: aiohttp.WSMessage,
):
    if message.type == aiohttp.WSMsgType.CLOSE:  # type: ignore
        return
    if message.type != aiohttp.WSMsgType.TEXT:  # type: ignore
        raise ProtocolError("Invalid message type")

    try:
        parsed: Dict[str, Any] = json.loads(message.data)  # type: ignore
    except json.JSONDecodeError:
        raise ProtocolError("JSON parse error")

    if not isinstance(parsed, dict):  # type: ignore
        raise ProtocolError("Invalid input")

    def parse_channels(key: str) -> List[pubsub.ChannelName]:
        value = parsed.pop(key)
        if isinstance(value, str):
            channels = [pubsub.ChannelName(value)]
        elif isinstance(value, list):
            if not all(isinstance(item, str) for item in cast(List[object], value)):
                raise ProtocolError(f"Invalid input: {key}")
            channels = [pubsub.ChannelName(name) for name in cast(List[str], value)]
        else:
            raise ProtocolError(f"Invalid input: {key}")
        if not channels:
            raise ProtocolError(f"Invalid input: {key}: no channels")
        if not all(channel for channel in channels):
            raise ProtocolError(f"Invalid input: {key}: empty channel name")
        return channels

    if "subscribe" in parsed:
        channels = parse_channels("subscribe")

        async def handle(
            channel_name: pubsub.ChannelName, message: pubsub.Message
        ) -> None:
            await handle_published(ws, channel_name, message)

        await asyncutils.gather(
            *(pubsub_client.subscribe(channel, handle) for channel in channels)
        )

        await ws.send_str(json.dumps({"subscribed": channels}))

    if "unsubscribe" in parsed:
        channels = parse_channels("unsubscribe")

        await asyncutils.gather(
            *(pubsub_client.unsubscribe(channel_name=channel) for channel in channels)
        )

        await ws.send_str(json.dumps({"unsubscribed": channels}))

    if parsed:
        await ws.send_str(
            json.dumps(
                {"warning": "Unsupported keys: " + ", ".join(sorted(parsed.keys()))}
            )
        )


async def serve(request: aiohttp.web.BaseRequest) -> aiohttp.web.StreamResponse:
    logger.debug("handling websocket connection: %s", request.method)

    if request.method != "GET":
        return aiohttp.web.Response(text="Invalid request method", status=400)

    ws = aiohttp.web.WebSocketResponse(protocols=("pubsub_1", "testing_1"))

    ws_ready = ws.can_prepare(request)
    if not ws_ready:
        raise aiohttp.web.HTTPBadRequest()

    protocol: Optional[str] = ws_ready.protocol  # type: ignore

    if protocol is None:
        return aiohttp.web.Response(text="Unsupported WebSocket protocol", status=400)

    await ws.prepare(request)

    def handle_disconnect():
        asyncio.ensure_future(
            ws.close(code=CODE_INTERNAL_ERROR, message=b"PubSub service disconnected")
        )

    async def handle_promiscuous(
        channel_names: Tuple[pubsub.ChannelName, ...], message: pubsub.Message
    ) -> None:
        await handle_published(ws, channel_names, message, promiscuous=True)

    async with pubsub.connect(
        "websocket", disconnected=handle_disconnect
    ) as pubsub_client:
        if protocol == "testing_1":
            await pubsub_client.subscribe_promiscuous(handle_promiscuous)

        # async def receieve_messages() -> None:
        #     while not req.response.closed:
        #         message = await req.response.receive()

        #         logger.debug("incoming: %r", message)

        #         try:
        #             await handle_incoming(req, pubsub_client, message)
        #         except ProtocolError as error:
        #             await req.closeWebSocketResponse(
        #                 code=CODE_PROTOCOL_ERROR, message=str(error)
        #             )
        #             break

        # async def heartbeat() -> None:
        #     while not req.response.closed:
        #         await asyncio.sleep(60)
        #         await req.response.ping()

        # done, pending = await asyncio.wait(
        #     [receieve_messages(), heartbeat()], return_when=asyncio.FIRST_COMPLETED
        # )

        while not ws.closed:
            message = await ws.receive()

            logger.debug("incoming: %r", message)

            try:
                await handle_incoming(ws, pubsub_client, message)
            except ProtocolError as error:
                await ws.close(code=CODE_PROTOCOL_ERROR, message=str(error).encode())
                break

    logger.debug("WebSocket connection finished")

    return ws
