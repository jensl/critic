import asyncio
import functools
import gzip
import logging
import logging.handlers
import pickle
import struct
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import base

from . import gateway
from .protocolbase import ClientBase, ConnectionClosed, ProtocolBase
from .binaryprotocol import (
    BinaryProtocolClient,
    BinaryProtocol,
    InputMessage,
    OutputMessage,
)
from .utils import ServiceError, ensure_service, is_background_service


class GatewayError(ServiceError):
    pass


class MessageChannel(Generic[InputMessage, OutputMessage]):
    __reading: Optional[asyncio.Future]
    client: BinaryProtocolClient[
        Union[gateway.Response, OutputMessage],
        Union[gateway.ForwardRequest, InputMessage],
    ]

    def __init__(
        self,
        service_name: str,
        *,
        loop: asyncio.AbstractEventLoop = None,
        dispatch_message: Callable[[Optional[OutputMessage]], Awaitable[None]] = None,
    ):
        self.service_name = service_name
        self.__loop = asyncio.get_event_loop() if loop is None else loop
        self.__connected = asyncio.ensure_future(self.__connect(), loop=self.loop)
        self.__reading = None
        self.__dispatch_message = dispatch_message

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self.__loop

    async def __connect(self) -> None:
        if not is_background_service():
            gateway_settings = api.critic.settings().services.gateway
            use_gateway = gateway_settings.enabled
        else:
            use_gateway = False

        if use_gateway:
            configuration = base.configuration()

            host = configuration["services.host"]
            port = configuration["services.port"]

            try:
                self.client = BinaryProtocolClient(
                    *await asyncio.open_connection(host, port)
                )
                await self.client.handshake(BinaryProtocol.PROTOCOL_PICKLE)
            except ConnectionRefusedError:
                raise GatewayError("Gateway service not responding")

            if self.service_name != "gateway":
                self.client.write_message(
                    gateway.ForwardRequest(gateway_settings.secret, self.service_name)
                )

                handshake_response = await self.client.read_message()

                if handshake_response is None:
                    raise GatewayError("Connection closed prematurely")
                elif not isinstance(handshake_response, gateway.Response):
                    raise GatewayError(
                        "Unexpected handshake response: {handshake_response!r}"
                    )
                elif handshake_response.status == "error":
                    raise GatewayError(
                        "Handshake failure: {handshake_response.message}"
                    )
        else:
            socket_path = ensure_service(self.service_name)

            logger.debug("connecting to %s...", socket_path)

            try:
                self.client = BinaryProtocolClient(
                    *await asyncio.open_unix_connection(socket_path, loop=self.loop)
                )
                await self.client.handshake(BinaryProtocol.PROTOCOL_PICKLE)
            except ConnectionRefusedError:
                raise ServiceError("Service not responding: %s" % self.service_name)

        async def dispatch_messages(
            dispatch: Callable[[Optional[OutputMessage]], Awaitable[None]]
        ) -> None:
            async for message in self.read_messages():
                await dispatch(message)
            await dispatch(None)

        if self.__dispatch_message:
            self.__reading = asyncio.create_task(
                dispatch_messages(self.__dispatch_message)
            )

    async def write_message(self, message: InputMessage) -> None:
        await self.__connected
        self.client.write_message(message)

    async def read_messages(self) -> AsyncIterator[OutputMessage]:
        while True:
            message = await self.client.read_message()
            if message is None:
                logger.debug("read_messages(): eof")
                asyncio.ensure_future(self.channel_closed(), loop=self.__loop)
                return
            assert not isinstance(message, gateway.Response)
            yield message

    async def run(self) -> None:
        await self.__connected
        if self.__reading:
            await self.__reading

    async def close(self) -> None:
        try:
            self.__connected.cancel()
            try:
                await self.__connected
            except asyncio.CancelledError:
                pass
        except Exception:
            if self.__reading:
                self.__reading.cancel()
        else:
            await self.client.disconnect()
        try:
            if self.__reading:
                logger.debug("waiting for reading to stop")
                await self.__reading
                logger.debug("reading stopped")
        except (asyncio.CancelledError, ConnectionClosed):
            pass

    def __aiter__(self) -> AsyncIterator[OutputMessage]:
        return self.read_messages()
