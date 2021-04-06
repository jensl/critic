from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)
import psycopg2
import psycopg2.extras
import threading
import time

logger = logging.getLogger(__name__)

from critic import base


class Stopped(Exception):
    pass


class Cursor(Protocol):
    def executemany(self, statement: str, values: Sequence[Sequence[object]]) -> None:
        ...


class Connection(Protocol):
    def cursor(self) -> Cursor:
        ...

    def commit(self) -> None:
        ...

    def close(self) -> None:
        ...


MAX_AGE = 0.5
MIN_AGE = 0.1


class Callback:
    def __init__(self, upstream: Callable[[], None], count: int):
        self.__upstream = upstream
        self.__count = count

    def __call__(self) -> None:
        self.__count -= 1
        if self.__count == 0:
            self.__upstream()


class Block(NamedTuple):
    argslist: Sequence[Sequence[object]]
    callback: Callback
    timestamp: float


class DatabaseUpdater(threading.Thread):
    __queue: Dict[str, List[Block]]
    __oldest_block: Dict[str, float]
    __newest_block: Dict[str, float]

    def __init__(self, callback: Callable[[], None]):
        super().__init__(target=self.__start, daemon=True)

        self.__condition = threading.Condition()
        self.__queue = defaultdict(list)
        self.__oldest_block = {}
        self.__newest_block = {}
        self.__stopped = False
        self.__callback = callback

    async def push(self, *statements: Tuple[str, Iterable[Sequence[object]]]) -> None:
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[None]" = loop.create_future()

        def callback():
            loop.call_soon_threadsafe(future.set_result, None)

        self.__push(statements, callback)

        await future

    def stop(self) -> None:
        with self.__condition:
            self.__stopped = True
            self.__condition.notify()
        self.join()

    def __push(
        self,
        statements: Sequence[Tuple[str, Iterable[Sequence[object]]]],
        callback: Callable[[], None],
    ) -> None:
        callback = Callback(callback, len(statements))
        with self.__condition:
            for statement, argslist in statements:
                if not self.__queue[statement]:
                    self.__oldest_block[statement] = time.time()
                self.__newest_block[statement] = time.time()
                self.__queue[statement].append(
                    Block([*argslist], callback, time.time())
                )
                self.__condition.notify()

    def __start(self) -> None:
        try:
            self.__run()
        except Exception:
            logger.exception("database updater thread crashed")
            self.__callback()
        else:
            logger.info("database updater thread stopped")

    def __run(self) -> None:
        connection: Optional[Connection] = None

        def connect() -> Connection:
            parameters = base.configuration()
            return psycopg2.connect(
                *parameters["database.parameters"]["args"],
                **parameters["database.parameters"]["kwargs"]
            )

        def get_statement() -> Tuple[str, Sequence[Block]]:
            nonlocal connection

            with self.__condition:
                while True:
                    if self.__stopped:
                        if connection:
                            connection.close()
                        raise Stopped()

                    now = time.time()
                    timeout = 60.0

                    for statement in self.__queue.keys():
                        oldest_age = now - self.__oldest_block[statement]
                        newest_age = now - self.__newest_block[statement]

                        if oldest_age > MAX_AGE or newest_age > MIN_AGE:
                            del self.__oldest_block[statement]
                            del self.__newest_block[statement]
                            return statement, self.__queue.pop(statement)

                        timeout = min(
                            timeout, MAX_AGE - oldest_age, MIN_AGE - newest_age
                        )

                    if not self.__condition.wait(timeout):
                        if not self.__queue and connection:
                            connection.close()
                            connection = None
                            logger.info("closed database connection")

        while True:
            try:
                statement, blocks = get_statement()
            except Stopped:
                return

            if connection is None:
                connection = connect()
                logger.info("opened database connection")

            argslist: List[Sequence[object]] = []
            callbacks = []

            for block in blocks:
                argslist.extend(block.argslist)
                callbacks.append(block.callback)

            while True:
                psycopg2.extras.execute_batch(connection.cursor(), statement, argslist)

                try:
                    connection.commit()
                except psycopg2.errors.IntegrityError:
                    logger.exception("integrity error")
                    connection.rollback()
                    continue

                break

            logger.info("Executed %d statements", len(argslist))

            for callback in callbacks:
                callback()
