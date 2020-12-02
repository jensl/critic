from __future__ import annotations

import aiohttp
import asyncio
import contextlib
import logging
import pytest
from typing import (
    Any,
    Dict,
    AsyncIterator,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    cast,
    overload,
)

from .frontend import Frontend
from ..utilities import Anonymizer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DictMatches:
    def __init__(self, checks: Dict[str, Any]):
        self.checks = {
            key: DictMatches(cast(Dict[str, Any], value))
            if isinstance(value, dict)
            else value
            for key, value in checks.items()
        }

    def __repr__(self) -> str:
        checks = (f"{name}={value!r}" for name, value in self.checks.items())
        return f"DictMatches({', '.join(checks)})"

    def __bool__(self) -> bool:
        return bool(self.checks)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, dict):
            return False
        for key, value in self.checks.items():
            if key not in other or value != other[key]:
                return False
        return True


class WebSocket:
    __connection: asyncio.Future[aiohttp.ClientWebSocketResponse]
    __messages: List[Any]

    def __init__(self, frontend: Frontend):
        self.__frontend = frontend
        self.__messages = []
        self.__connection = asyncio.Future()
        self.__task = asyncio.create_task(self.__run())
        self.__closed = False
        self.__condition = asyncio.Condition()

    @property
    def frontend(self) -> Frontend:
        return self.__frontend

    async def close(self) -> List[Any]:
        if not self.__closed:
            self.__closed = True
            await (await self.__connection).close()
            await self.__task
        return self.__messages

    async def __run(self) -> None:
        async with self.frontend.client_session.ws_connect(
            f"{self.frontend.prefix}/ws", protocols=("testing_1",)
        ) as connection:
            self.__connection.set_result(connection)
            async for msg in connection:
                logger.debug("websocket message: %r", msg)
                async with self.__condition:
                    try:
                        self.__messages.append(msg.json()["publish"])
                    except Exception as error:
                        self.__messages.append(str(error))
                    self.__condition.notify_all()

    @staticmethod
    @contextlib.asynccontextmanager
    async def connect(
        frontend: Frontend, anonymizer: Anonymizer, snapshot: Any
    ) -> AsyncIterator[WebSocket]:
        websocket = WebSocket(frontend)
        await websocket.__connection
        try:
            yield websocket
        finally:
            logger.debug("closing websocket")
            messages = await websocket.close()
        snapshot.assert_match(anonymizer({"publish": messages}), "websocket messages")

    @overload
    async def __find(
        self, channel: Optional[str], match: DictMatches
    ) -> Tuple[int, Dict[str, Any]]:
        ...

    @overload
    async def __find(
        self,
        channel: Optional[str],
        match: DictMatches,
        *,
        block: Literal[False],
    ) -> Optional[Tuple[int, Dict[str, Any]]]:
        ...

    async def __find(
        self,
        channel: Optional[str],
        match: DictMatches,
        *,
        block: bool = True,
    ) -> Optional[Tuple[int, Dict[str, Any]]]:
        logger.debug("looking for: %r", match)

        def find() -> Optional[Tuple[int, Dict[str, Any]]]:
            for index, publish in enumerate(self.__messages):
                if channel is not None and channel not in publish["channel"]:
                    continue
                message = publish["message"]
                if match and match != message:
                    continue
                logger.debug("found matching message: %r", message)
                return index, message
            return None

        async def find_blocking() -> Tuple[int, Dict[str, Any]]:
            async with self.__condition:
                while True:
                    if found := find():
                        return found
                    await self.__condition.wait()

        if block:
            try:
                return await asyncio.wait_for(find_blocking(), timeout=60)
            except asyncio.TimeoutError:
                assert False, f"message not found: {channel=} {match=}"

        return find()

    async def expect(self, channel: Optional[str] = None, /, **checks: Any) -> Any:
        logger.debug("looking for: %r", checks)
        _, message = await self.__find(channel, DictMatches(checks))
        return message

    async def expect_noblock(
        self, channel: Optional[str] = None, /, **checks: Any
    ) -> Any:
        logger.debug("looking for: %r", checks)
        if found := await self.__find(channel, DictMatches(checks), block=False):
            _, message = found
            return message
        return None

    async def pop(self, channel: Optional[str] = None, /, **checks: Any) -> Any:
        logger.debug("looking for: %r", checks)
        index, message = await self.__find(channel, DictMatches(checks))
        del self.__messages[index]
        return message

    async def pop_noblock(self, channel: Optional[str] = None, /, **checks: Any) -> Any:
        logger.debug("looking for: %r", checks)
        if found := await self.__find(channel, DictMatches(checks), block=False):
            index, message = found
            del self.__messages[index]
            return message
        return None


@pytest.fixture
async def websocket(
    frontend: Frontend, anonymizer: Anonymizer, snapshot: Any
) -> AsyncIterator[WebSocket]:
    async with WebSocket.connect(frontend, anonymizer, snapshot) as websocket:
        yield websocket
