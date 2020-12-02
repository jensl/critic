from __future__ import annotations

import asyncio
import logging
import os
import pickle
import struct
import sys
import traceback
from typing import AsyncIterator, Optional, Protocol, Set

logger = logging.getLogger(__name__)

from .arguments import Arguments

HEADER_FMT = "!I"


class System(Protocol):
    arguments: Arguments
    criticctl_path: Optional[str]
    server_host: Optional[str]
    server_port: int
    state_dir: str

    async def restart(self) -> bool:
        ...


class ControlPipe(logging.Handler):
    class Client:
        def __init__(
            self,
            reader: asyncio.StreamReader,
            writer: Optional[asyncio.StreamWriter] = None,
        ):
            self.reader = reader
            self.writer = writer
            self.disabled = False

        async def write(self, item: object) -> None:
            assert self.writer is not None
            if self.disabled:
                return
            if isinstance(item, bytes):
                data = item
            else:
                data = pickle.dumps(item)
            try:
                self.writer.write(struct.pack(HEADER_FMT, len(data)) + data)
                await self.writer.drain()
            except ConnectionResetError:
                self.disabled = True
            except Exception:
                traceback.print_exc(file=sys.stderr)
                self.disabled = True

        async def read(self) -> AsyncIterator[object]:
            while True:
                try:
                    header = await self.reader.readexactly(struct.calcsize(HEADER_FMT))
                except asyncio.IncompleteReadError as error:
                    assert not error.partial, error.partial
                    break
                except ConnectionError:
                    break
                data_len: int = struct.unpack(HEADER_FMT, header)[0]
                try:
                    data = await self.reader.readexactly(data_len)
                except asyncio.IncompleteReadError as error:
                    logger.debug("partial: %r", error.partial)
                    raise
                # print(f"read {len(data)} bytes", file=sys.stderr)
                try:
                    yield pickle.loads(data)
                except Exception:
                    logger.exception("unpickle failure!")
                    # logger.debug("data: %d/%d %r", data_len, len(data), data)

    clients: Set[Client]

    def __init__(self, system: System):
        super().__init__()

        self.system = system
        self.clients = set()

        logging.getLogger().addHandler(self)

        self.task = asyncio.create_task(self.run())

    def write(self, item: object) -> None:
        if self.clients:
            data = pickle.dumps(item)
            for client in self.clients:
                try:
                    asyncio.create_task(client.write(data))
                except RuntimeError:
                    pass

    async def client_connected(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        logger.debug("client connected")

        client = self.Client(reader, writer)
        self.clients.add(client)

        async def initialize():
            await client.write(
                {
                    "root_dir": self.system.arguments.root_dir,
                    "criticctl_path": self.system.criticctl_path,
                }
            )
            if self.system.server_host:
                await client.write(
                    {
                        "http": (
                            self.system.server_host,
                            self.system.server_port,
                        )
                    }
                )

        asyncio.create_task(initialize())

        async for msg in client.read():
            if isinstance(msg, dict):
                if "request" in msg and msg["request"] == "restart":
                    await self.system.restart()

        logger.debug("client disconnected")
        self.clients.remove(client)

    async def run(self) -> None:
        self.server = await asyncio.start_unix_server(
            self.client_connected,
            path=os.path.join(self.system.state_dir, "controlpipe.unix"),
        )
        await self.server.serve_forever()

    def emit(self, record: logging.LogRecord) -> None:
        self.write(
            {
                "log": {
                    "level": record.levelno,
                    "name": record.name,
                    "message": record.msg % record.args if record.args else record.msg,
                    "traceback": (
                        "".join(traceback.format_exception(*record.exc_info))  # type: ignore
                        if record.exc_info
                        else None
                    ),
                }
            }
        )
