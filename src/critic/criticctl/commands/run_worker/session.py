from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable, AsyncIterator, Optional, Protocol, Tuple, TypeVar

from critic import api


T = TypeVar("T", covariant=True)


class Command(Protocol[T]):
    async def __call__(self, critic: api.critic.Critic) -> T:
        ...


class Session:
    __queue: "asyncio.Queue[Optional[Tuple[Command[Any], asyncio.Future[Any]]]]"

    def __init__(self) -> None:
        self.__queue = asyncio.Queue()

    async def execute(self, command: Command[T]) -> T:
        future = asyncio.get_running_loop().create_future()
        await self.__queue.put((command, future))
        return await future

    async def __run(self):
        async with api.critic.startSession(for_system=True) as critic:
            while True:
                item = await self.__queue.get()

                if item is None:
                    return

                command, future = item

                try:
                    future.set_result(await command(critic))
                except Exception as error:
                    future.set_exception(error)

    @staticmethod
    @asynccontextmanager
    async def start() -> AsyncIterator[Session]:
        session = Session()
        task = asyncio.create_task(session.__run())
        try:
            yield session
        finally:
            await session.__queue.put(None)
            await task
