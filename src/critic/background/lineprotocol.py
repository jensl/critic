import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Tuple, TypeVar, Optional, cast

logger = logging.getLogger(__name__)

from .protocolbase import ClientBase, ProtocolBase


async def read_lines(
    reader: asyncio.StreamReader, handle_line: Callable[[str], Awaitable[None]]
) -> None:
    while True:
        line = await reader.readline()
        if not line:
            return
        logger.debug(f"{line=}")
        if not line.endswith(b"\n"):
            raise Exception("Unexpected EOF")
        await handle_line(line[:-1].decode())


async def write_lines(
    writer: asyncio.StreamWriter,
    queue: "asyncio.Queue[Optional[Tuple[str, asyncio.Future[bool]]]]",
) -> None:
    while True:
        item = await queue.get()
        if item is None:
            logger.debug(f"closing pipe")
            writer.close()
            await writer.wait_closed()
            return
        (line, future) = item
        line_sent = False
        try:
            logger.debug(f"writing {line=}")
            writer.write(line.encode() + b"\n")
            await writer.drain()
            line_sent = True
        finally:
            future.set_result(line_sent)


class LineProtocolClient(ClientBase, ABC):
    outgoing: "asyncio.Queue[Optional[Tuple[str, asyncio.Future[bool]]]]"

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ):
        super().__init__(reader, writer)
        self.outgoing = asyncio.Queue()

    @abstractmethod
    async def handle_line(self, line: str) -> None:
        ...

    async def write_line(self, line: str) -> "asyncio.Future[bool]":
        future: "asyncio.Future[bool]" = asyncio.get_running_loop().create_future()
        await self.outgoing.put((line, future))
        return future

    async def close(self) -> None:
        await self.outgoing.put(None)

    async def run(self) -> None:
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(
                    read_lines(self.reader, self.handle_line), name="read_lines()"
                ),
                asyncio.create_task(
                    write_lines(self.writer, self.outgoing), name="write_lines()"
                ),
            ],
            return_when=asyncio.ALL_COMPLETED,
        )

        for task in done | pending:
            if task in pending:
                task.cancel()
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Task %s failed!", cast(asyncio.Task, task).get_name())

        while not self.outgoing.empty():
            item = self.outgoing.get_nowait()
            if item:
                (_, future) = item
                future.set_result(False)


LineClientType = TypeVar("LineClientType", bound=LineProtocolClient)


class LineProtocol(ProtocolBase[LineClientType]):
    manage_socket = True

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client = self.create_client(reader, writer)
        client.ensure_future(client.run())
        self._add_client(client)
        client.ensure_future(client.handle_connected())
