from __future__ import annotations

import aiohttp
import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import logging
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Set, Tuple

logger = logging.getLogger(__name__)

from .arguments import get as get_arguments

websocket: ContextVar[WebSocket] = ContextVar("WebSocket")


class WebSocket:
    __run_task: "asyncio.Task[None]"
    __connection: "asyncio.Future[aiohttp.ClientWebSocketResponse]"
    __messages: Dict[str, List[Any]]

    def __init__(self):
        self.url = f"{get_arguments().backend.rstrip('/')}/ws"
        self.protocol = "pubsub_1"
        self.__condition = asyncio.Condition()
        self.__subscriptions = Set[str]
        self.__messages = {}

    async def __run(self) -> None:
        async with aiohttp.ClientSession() as client_session:
            async with client_session.ws_connect(
                self.url, protocols=(self.protocol,)
            ) as connection:
                self.__connection.set_result(connection)
                async for msg in connection:
                    logger.debug("websocket message: %r", msg)
                    async with self.__condition:
                        json = msg.json()
                        if "publish" in json:
                            publish = msg.json()["publish"]
                            self.__messages[publish["channel"]].append(
                                publish["message"]
                            )
                        elif "subscribed":
                            self.__subscriptions.update(json["subscribed"])
                        elif "unsubscribed":
                            self.__subscriptions.difference_update(json["unsubscribed"])
                        self.__condition.notify_all()

    async def connect(self) -> None:
        self.__connection = asyncio.get_running_loop().create_future()
        self.__run_task = asyncio.create_task(self.__run())

        await self.__connection

    async def disconnect(self) -> None:
        self.__run_task.cancel()

    @staticmethod
    def __find(
        messages: List[Any], offset: int, /, **match: object
    ) -> Tuple[int, Optional[Mapping[str, Any]]]:
        index = 0
        for index, message in enumerate(messages[offset:]):
            for key, value in match.items():
                if key not in message or value != message[key]:
                    break
            else:
                return (offset + index, message)
        else:
            return (offset + index, None)

    def __expect(
        self, messages: List[Any], **match: object
    ) -> "asyncio.Future[Mapping[str, Any]]":
        async def wait(offset: int) -> Mapping[str, Any]:
            while True:
                async with self.__condition:
                    offset, message = self.__find(messages, offset, **match)
                    if message is not None:
                        return message
                    await self.__condition.wait()

        return asyncio.create_task(wait(len(messages)))

    async def expect(self, channel_name: str, /, **match: object) -> Mapping[str, Any]:
        async def expect_subscription() -> None:
            while True:
                if channel_name in self.__subscriptions:
                    return
                await self.__condition.wait()

        message: "asyncio.Future[Mapping[str, Any]]"

        async with self.__condition:
            if not channel_name in self.__messages:
                messages = self.__messages[channel_name] = []
                message = self.__expect(messages, **match)
                await (await self.__connection).send_json({"subscribe": channel_name})
                await expect_subscription()
            else:
                message = self.__expect(self.__messages[channel_name], **match)

        return await message


@asynccontextmanager
async def connect() -> AsyncIterator[WebSocket]:
    token = websocket.set(WebSocket())
    await get().connect()

    try:
        yield get()
    finally:
        await get().disconnect()
        websocket.reset(token)


def get() -> WebSocket:
    return websocket.get()
