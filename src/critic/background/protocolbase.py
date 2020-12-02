from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Generic, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

ClientType = TypeVar("ClientType", bound="ClientBase")


class ConnectionClosed(Exception):
    pass


class ClientBase:
    tasks: Set["asyncio.Future[Any]"]

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.reader = reader
        self.writer = writer
        self.tasks = set()

    def ensure_future(self, coroutine: Awaitable[T]) -> "asyncio.Future[T]":
        future = asyncio.ensure_future(coroutine)
        future.add_done_callback(lambda future: self.tasks.remove(future))
        self.tasks.add(future)
        return future

    def check_future(self, coroutine: Awaitable[T]) -> "asyncio.Future[T]":
        def check(future: "asyncio.Future[T]") -> None:
            try:
                future.result()
            except Exception:
                logger.exception("Checked coroutine failed!")

        future = self.ensure_future(coroutine)
        future.add_done_callback(check)
        return future

    async def handle_connected(self) -> None:
        pass


class ProtocolBase(Generic[ClientType], ABC):
    clients: Set[ClientType]

    def __init__(self) -> None:
        self.clients = set()

    def handle_connection(self) -> asyncio.StreamReaderProtocol:
        return asyncio.StreamReaderProtocol(asyncio.StreamReader(), self.handle_client)

    @abstractmethod
    def create_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> ClientType:
        ...

    @abstractmethod
    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        ...

    def client_connected(self, client: ClientType) -> None:
        pass

    def client_disconnected(self, client: ClientType) -> None:
        pass

    def _add_client(self, client: ClientType) -> None:
        self.clients.add(client)
        self.client_connected(client)

    def _remove_client(self, client: ClientType) -> None:
        self.clients.remove(client)
        self.client_disconnected(client)
