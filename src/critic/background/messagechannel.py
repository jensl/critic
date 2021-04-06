import asyncio
import logging
import logging.handlers
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Optional,
    Union,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import base

from . import gateway
from .protocolbase import ConnectionClosed
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
    __reading: Optional["asyncio.Future[None]"]
    client: BinaryProtocolClient[
        Union[gateway.Response, OutputMessage],
        Union[gateway.ForwardRequest, InputMessage],
    ]

    def __init__(
        self,
        service_name: str,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        dispatch_message: Optional[
            Callable[[Optional[OutputMessage]], Awaitable[None]]
        ] = None,
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
        else:
            gateway_settings = None

        if gateway_settings and gateway_settings.enabled:
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
            try:
                async for message in self.read_messages():
                    await dispatch(message)
            except ConnectionClosed:
                pass
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
                asyncio.create_task(self.channel_closed())
                return
            assert not isinstance(message, gateway.Response)
            yield message

    async def run(self) -> None:
        await self.__connected
        if self.__reading:
            await self.__reading

    async def close(self) -> None:
        try:
            if not self.__connected.done():
                self.__connected.cancel()
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

    async def channel_closed(self) -> None:
        pass

    def __aiter__(self) -> AsyncIterator[OutputMessage]:
        return self.read_messages()
