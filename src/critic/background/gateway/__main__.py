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

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Literal, Optional, Tuple, TypedDict

logger = logging.getLogger("critic.background.gateway")

from . import RequestBase, ForwardRequest, WakeUpRequest, Response
from ..binaryprotocol import BinaryProtocolClient, BinaryProtocol
from ..protocolbase import ConnectionClosed
from ..service import BackgroundService
from ..utils import ServiceError, ensure_service, WakeUpError

from critic import background


async def forward_stream(source: GatewayClient, target: GatewayClient) -> None:
    try:
        while True:
            target.write_raw_message(await source.read_raw_message())
    except ConnectionClosed:
        pass
    finally:
        await target.disconnect()


class GatewayClient(BinaryProtocolClient[Any, Any]):
    def __init__(
        self,
        service: GatewayService,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        super().__init__(reader, writer)
        self.service = service

    async def start(self, dispatch: Callable[[Any], AsyncIterator[Any]]) -> None:
        request = await self.read_message()

        def reject(message: str) -> None:
            logger.error(message)
            self.disconnect()
            return

        if request is None:
            return reject("Connection closed prematurely")

        if not isinstance(request, RequestBase):
            return reject(f"Unexpected handshake: {request!r}")

        if self.service.secret and request.secret != self.service.secret:
            return reject("Client provided an invalid secret")

        try:
            if isinstance(request, ForwardRequest):
                await self.service.forward(self, request)
            elif isinstance(request, WakeUpRequest):
                await self.service.wakeup(self, request)
            else:
                return reject(f"Unexpected input: {request!r}")
        except Exception:
            logger.exception("failed to handle client")


class GatewayService(BackgroundService, BinaryProtocol[GatewayClient, Any, Any]):
    name = "gateway"

    def create_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> GatewayClient:
        return GatewayClient(self, reader, writer)

    async def forward(self, client: GatewayClient, request: ForwardRequest) -> None:
        logger.debug("forwarding client to service: %s", request.service_name)

        def reject(message: str) -> None:
            logger.warning("Rejecting client forward request: %s", message)
            client.write_message(Response("error", message))
            client.disconnect()

        try:
            socket_path = ensure_service(request.service_name)
        except ServiceError as error:
            return reject(str(error))

        try:
            reader, writer = await asyncio.open_unix_connection(socket_path)
        except ConnectionRefusedError:
            return reject(f"Service not responding: {request.service_name}")

        client.write_message(Response("ok"))

        upstream = GatewayClient(self, reader, writer)
        upstream.ensure_future(forward_stream(client, upstream))
        upstream.ensure_future(forward_stream(upstream, client))
        self.clients.add(upstream)

    async def wakeup(self, client: GatewayClient, request: WakeUpRequest) -> None:
        logger.debug("waking up service: %s", request.service_name)

        try:
            background.utils.wakeup_direct(request.service_name)
        except WakeUpError as error:
            response = Response("error", str(error))
        else:
            response = Response("ok")

        client.write_message(response)
        client.disconnect()

    @staticmethod
    def socket_path() -> None:
        return None

    @classmethod
    def socket_address(cls) -> Tuple[str, int]:
        address = cls.service_settings.address
        return (address.host, address.port)

    def will_start(self) -> bool:
        return self.service_settings.enabled

    @property
    def secret(self) -> str:
        return self.service_settings.secret


if __name__ == "__main__":
    background.service.call(GatewayService)
