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

from .protocolbase import ClientBase, ConnectionClosed, ProtocolBase

EncodeFunction = Callable[[Any], bytes]
DecodeFunction = Callable[[bytes], Any]

InputMessage = TypeVar("InputMessage")
OutputMessage = TypeVar("OutputMessage")


# class Dispatch(Protocol[InputMessage, OutputMessage]):
#    def __call__(self, message: InputMessage) -> AsyncIterator[OutputMessage]:
#        ...


def decode_pickle(data: bytes) -> Any:
    return pickle.loads(data)


def encode_pickle(data: Any) -> bytes:
    return pickle.dumps(data)


RawMessage = Tuple[int, bytes]


class BinaryProtocolClient(Generic[InputMessage, OutputMessage], ClientBase):
    protocol_id: Optional[int]
    __encode_message: Optional[EncodeFunction]
    __decode_message: Optional[DecodeFunction]
    outgoing: "asyncio.Queue[OutputMessage]"
    __disconnected: Optional["asyncio.Future[None]"]
    was_disconnected: "asyncio.Future[None]"

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ):
        super().__init__(reader, writer)
        self.protocol_id = None
        self.__encode_message = None
        self.__decode_message = None
        self.outgoing = asyncio.Queue()
        self.tasks = set()
        self.__disconnected = None
        self.was_disconnected = asyncio.Future()

    def encode_message(self, message: OutputMessage) -> bytes:
        assert self.__encode_message
        return self.__encode_message(message)

    def decode_message(self, message_data: bytes) -> InputMessage:
        assert self.__decode_message
        return self.__decode_message(message_data)

    def select_protocol(self, protocol_id: int) -> None:
        if protocol_id == BinaryProtocol.PROTOCOL_PICKLE:
            self.__encode_message = encode_pickle
            self.__decode_message = decode_pickle
        else:
            raise Exception("Invalid protocol id!")
        self.protocol_id = protocol_id

    async def start(
        self, dispatch: Callable[[InputMessage], AsyncIterator[OutputMessage]]
    ) -> None:
        self.ensure_future(self.write_messages())
        self.ensure_future(self.read_messages(dispatch))

    async def handshake(self, protocol_id: int) -> None:
        self.writer.write(BinaryProtocol.encode_handshake(protocol_id))
        self.select_protocol(protocol_id)

    async def read_raw_message(self) -> RawMessage:
        try:
            header = await self.reader.readexactly(BinaryProtocol.HEADER_SIZE)
        except asyncio.IncompleteReadError as error:
            if error.partial:
                raise
            raise ConnectionClosed()
        except ConnectionError:
            raise ConnectionClosed()
        size, flags = struct.unpack(BinaryProtocol.HEADER_FORMAT, header)
        data = await self.reader.readexactly(size)
        return flags, data

    async def read_message(self) -> InputMessage:
        flags, data = await self.read_raw_message()
        if (flags & BinaryProtocol.FLAG_GZIP) == BinaryProtocol.FLAG_GZIP:
            data = gzip.decompress(data)
        return self.decode_message(data)

    async def read_messages(
        self, dispatch: Callable[[InputMessage], AsyncIterator[OutputMessage]]
    ) -> None:
        try:
            while True:
                self.ensure_future(
                    self.handle_message(dispatch, await self.read_message())
                )
        except ConnectionClosed:
            pass
        finally:
            self.disconnect()

    async def handle_message(
        self,
        dispatch: Callable[[InputMessage], AsyncIterator[OutputMessage]],
        input_message: InputMessage,
    ) -> None:
        try:
            async for output_message in dispatch(input_message):
                await self.outgoing.put(output_message)
        except Exception:
            logger.exception("Crash in message dispatch!")
            self.disconnect()

    def write_raw_message(self, message: RawMessage) -> None:
        flags, data = message
        self.writer.write(
            struct.pack(BinaryProtocol.HEADER_FORMAT, len(data), flags) + data
        )

    def write_message(self, message: OutputMessage) -> None:
        data = self.encode_message(message)
        flags = 0
        if len(data) > BinaryProtocol.GZIP_THRESHOLD:
            data = gzip.compress(data, 1)
            flags = flags | BinaryProtocol.FLAG_GZIP
        self.write_raw_message((flags, data))

    async def write_messages(self) -> None:
        while True:
            message = await self.outgoing.get()
            try:
                self.write_message(message)
            except Exception:
                logger.exception("Crash in BinaryProtocol.Client.write_message()!")
                break
        self.disconnect()

    def disconnect(self) -> "asyncio.Future[None]":
        async def do_disconnect() -> None:
            await self.disconnecting()
            self.writer.close()
            if hasattr(self.writer, "wait_closed"):
                await self.writer.wait_closed()
            if self.tasks:
                for task in self.tasks:
                    task.cancel()
            self.was_disconnected.set_result(None)
            await self.disconnected()

        if self.__disconnected is None:
            self.__disconnected = asyncio.ensure_future(do_disconnect())
        return self.__disconnected

    async def disconnecting(self) -> None:
        pass

    async def disconnected(self) -> None:
        pass


BinaryClientType = TypeVar("BinaryClientType", bound=BinaryProtocolClient)


class BinaryProtocol(
    Generic[BinaryClientType, InputMessage, OutputMessage],
    ProtocolBase[BinaryClientType],
):
    manage_socket = True

    PROTOCOL_PICKLE = 1
    VALID_PROTOCOLS = {PROTOCOL_PICKLE}

    HANDSHAKE_MAGIC = b"Critic2"
    HANDSHAKE_FORMAT = f"!{len(HANDSHAKE_MAGIC)}sB"
    HANDSHAKE_SIZE = struct.calcsize(HANDSHAKE_FORMAT)

    @staticmethod
    def encode_handshake(protocol_id: int) -> bytes:
        return struct.pack(
            BinaryProtocol.HANDSHAKE_FORMAT, BinaryProtocol.HANDSHAKE_MAGIC, protocol_id
        )

    @staticmethod
    def decode_handshake(data: bytes) -> int:
        if len(data) != BinaryProtocol.HANDSHAKE_SIZE:
            raise Exception("Invalid handshake: %r", data)
        magic, protocol_id = struct.unpack(BinaryProtocol.HANDSHAKE_FORMAT, data)
        if magic != BinaryProtocol.HANDSHAKE_MAGIC:
            raise Exception("Invalid handshake magic: %r", magic)
        if protocol_id not in BinaryProtocol.VALID_PROTOCOLS:
            raise Exception("Invalid handshake protocol: %r", protocol_id)
        return protocol_id

    HEADER_FORMAT = "!IB"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    GZIP_THRESHOLD = 256
    FLAG_GZIP = 1 << 0

    message_encoding = None

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        handshake = await reader.readexactly(BinaryProtocol.HANDSHAKE_SIZE)
        if not handshake:
            logger.debug("empty handshake!")
            writer.close()
            return
        try:
            protocol_id = BinaryProtocol.decode_handshake(handshake)
        except Exception:
            logger.exception("Misbehaving client:")
            writer.close()
            return

        client = self.create_client(reader, writer)
        client.select_protocol(protocol_id)
        client.was_disconnected.add_done_callback(
            lambda task: self.handle_client_disconnected(client)
        )
        self._add_client(client)
        client.ensure_future(
            client.start(functools.partial(self.dispatch_message, client))
        )
        client.ensure_future(client.handle_connected())

    async def handle_client_connected(self, client: BinaryClientType) -> None:
        pass

    def handle_client_disconnected(self, client: BinaryClientType) -> None:
        self._remove_client(client)

    def dispatch_message(
        self, client: BinaryClientType, message: InputMessage
    ) -> AsyncIterator[OutputMessage]:
        raise Exception("must be overridden")

    async def will_stop(self) -> None:
        await asyncio.gather(*(client.disconnect() for client in self.clients))
