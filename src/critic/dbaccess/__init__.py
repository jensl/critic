# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections import defaultdict
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Collection,
    Coroutine,
    DefaultDict,
    Generator,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

logger = logging.getLogger(__name__)

from critic import base
from .formatter import StatementFormatter
from .lowlevel import LowLevelCursor, LowLevelConnection, LowLevelConnectionPool
from .types import (
    Adaptable,
    ExecuteArguments,
    Parameter,
    Parameters,
    SQLRow,
    SQLValue,
    adapt,
    parameters,
)
from .utils import analyze_query


_pool: Optional[LowLevelConnectionPool] = None
_formatter: Optional[StatementFormatter] = None


def pretty(sql: str) -> str:
    return re.sub(r"\s\s+", " ", sql)


class Error(Exception):
    pass


class ZeroRowsInResult(Error):
    pass


class MultipleRowsInResult(Error):
    pass


class MultipleColumnsInResult(Error):
    pass


class DetachedResultSet(Error):
    pass


class Deadlock(Error):
    """Attempt to execute a nested command in the same asyncio.Task

    Executing a command in a different task will block until the current
    command has finished. This can potentially also be a deadlock situation,
    but that is not detected."""

    pass


class TransactionInterference(Error):
    """Attempt to execute a command from a different asyncio.Task

    This is raised when a transaction is active, and a different asyncio.Task
    than the one that started the transaction tries to execute some command.
    Typically, an active transaction should mean exclusive access to the
    database."""

    pass


class Accounting:
    class Statement:
        count: int
        accumulated_time: float
        accumulated_rows: int
        maximum_time: float
        maximum_rows: int

        def __init__(self) -> None:
            self.count = 0
            self.accumulated_time = 0
            self.accumulated_rows = 0
            self.maximum_time = 0
            self.maximum_rows = 0

        def record(self, time: float, rows: int) -> None:
            self.count += 1
            self.accumulated_time += time
            self.accumulated_rows += rows
            self.maximum_time = max(self.maximum_time, time)
            self.maximum_rows = max(self.maximum_rows, rows)

    per_statement: DefaultDict[str, Statement]

    def __init__(self) -> None:
        self.per_statement = defaultdict(Accounting.Statement)

    def record(self, statement: str, time: float, rows: int) -> None:
        self.per_statement[statement].record(time, rows)


class Token:
    pass


class Connection:
    __transaction: Optional[Transaction]
    __lock: asyncio.Lock
    __locked_by: Optional["asyncio.Task[Any]"]
    __locked_token: Optional[Token]
    __accounting: Optional[Accounting]

    def __init__(
        self, low_level: LowLevelConnection, formatter: StatementFormatter
    ) -> None:
        self.formatter = formatter
        self.__low_level = low_level
        self.__transaction = None
        self.__lock = asyncio.Lock()
        self.__locked_by = None
        self.__locked_token = None
        self.__accounting = None

    def enable_accounting(self) -> None:
        self.__accounting = Accounting()

    @property
    def executed_statements(self) -> Iterator[Tuple[str, Accounting.Statement]]:
        assert self.__accounting
        return iter(
            sorted(
                self.__accounting.per_statement.items(),
                key=lambda item: item[1].accumulated_time,
                reverse=True,
            )
        )

    @contextlib.contextmanager
    def record_statement(
        self, statement: str
    ) -> Iterator[Callable[[Union[int, ResultSet[Any]]], None]]:
        def do_nothing(rows: Union[int, ResultSet[Any]]) -> None:
            pass

        if self.__accounting is None:
            yield do_nothing
            return

        def set_rows(rows: Union[int, ResultSet[Any]]) -> None:
            after = time.clock_gettime(time.CLOCK_REALTIME)
            assert self.__accounting
            if isinstance(rows, ResultSet):
                rows = rows.count()
            self.__accounting.per_statement[pretty(statement)].record(
                after - before, rows
            )

        before = time.clock_gettime(time.CLOCK_REALTIME)
        yield set_rows

    def check_transaction(self, cursor: BasicCursor) -> None:
        if not self.__transaction:
            raise Exception("no current transaction")
        if not self.__transaction.started:
            raise Exception("transaction not started yet")
        if not self.__transaction.is_allowed_task():
            raise Exception("using transaction from other task")
        if not self.__transaction.is_allowed_cursor(cursor):
            raise Exception("wrong cursor used during transaction")

    def check_statement(self, cursor: BasicCursor, statement: str) -> None:
        command = analyze_query(statement)
        if command not in ("INSERT", "UPDATE", "DELETE"):
            raise Exception("invalid statement: %s" % statement)
        self.check_transaction(cursor)

    def check_query(
        self,
        cursor: BasicCursor,
        query: str,
        for_update: Optional[bool] = None,
        returning: Optional[str] = None,
    ) -> None:
        try:
            command = analyze_query(query)
            if command not in ("SELECT", "INSERT"):
                raise Exception("invalid query: %s" % query)
            if for_update and command != "SELECT":
                raise Exception("invalid use of `for_update`")
            if for_update or command == "INSERT":
                self.check_transaction(cursor)
            if command == "INSERT" and returning is None:
                raise Exception("invalid query: must use `returning`")
        except Exception:
            logger.error("invalid query: %r", query)
            raise

    def cursor(self, token: Optional[Token] = None) -> BasicCursor:
        return BasicCursor(self, self.__low_level.cursor, token)

    @contextlib.asynccontextmanager
    async def query(
        self, query: str, **parameters: Parameters
    ) -> AsyncIterator[ResultSet[SQLRow]]:
        cursor: BasicCursor

        # If we have an current transaction, return the cursor that belongs to
        # it.
        if self.__transaction:
            cursor = self.__transaction.cursor
            async with cursor.query(query, **parameters) as result:
                yield result
            return

        # Otherwise, create a temporary cursor for the query. Lock the database
        # to avoid a race where the cursor automatically closes between being
        # created and the subsequent use of it.
        async with self.lock("database.query") as token:
            cursor = self.cursor(token)
            async with cursor.query(query, **parameters) as result:
                yield result

    def transaction(self) -> Transaction:
        if self.__transaction:
            raise Exception("Already in a transaction!")

        async def start() -> None:
            self.__transaction = transaction

        def reset() -> None:
            self.__transaction = None

        transaction = Transaction(self, self.__low_level, start, reset)
        return transaction

    @property
    def in_transaction(self) -> bool:
        return self.__transaction is not None

    @contextlib.asynccontextmanager
    async def lock(
        self, description: str, token: Optional[Token] = None
    ) -> AsyncIterator[Optional[Token]]:
        current_task = asyncio.current_task()
        if current_task is self.__locked_by:
            if token == self.__locked_token:
                yield token
                return
            logger.warning("Task %r is deadlocked!", current_task)
            logger.warning("Locking: %s", self.__locked_description)
            logger.warning("Current: %s", description)
            raise Deadlock()
        acquired = False

        async def acquire() -> None:
            nonlocal acquired
            assert not acquired
            await self.__lock.acquire()
            acquired = True

        def release() -> None:
            nonlocal acquired
            assert acquired
            self.__lock.release()
            acquired = False

        try:
            while True:
                await acquire()
                assert self.__locked_by is None
                if self.__transaction:
                    if not self.__transaction.is_allowed_task():
                        # Wait for the transaction to end.
                        release()
                        await self.__transaction.wait()
                        continue
                self.__locked_by = current_task
                self.__locked_description = description
                self.__locked_token = Token()
                yield self.__locked_token
                return
        finally:
            if acquired:
                assert self.__locked_by in (None, current_task)
                self.__locked_by = None
                release()

    async def close(self) -> None:
        await self.__low_level.close()


class BasicCursor:
    ZeroRowsInResult = ZeroRowsInResult
    MultipleRowsInResult = MultipleRowsInResult
    MultipleColumnsInResult = MultipleColumnsInResult

    def __init__(
        self,
        connection: Connection,
        low_level: LowLevelCursor,
        token: Optional[Token] = None,
    ) -> None:
        self._connection = connection
        self._low_level = low_level
        self._token = token

    def _prepare(
        self, sql: str, parameters: Parameters, **kwargs: Any
    ) -> Tuple[str, ExecuteArguments]:
        return self._connection.formatter.format(sql, parameters, **kwargs)

    @contextlib.asynccontextmanager
    async def query(
        self, query: str, **kwargs: Parameter
    ) -> AsyncIterator[ResultSet[SQLRow]]:
        if self._low_level is None:
            raise Exception("Closed cursor used.")
        formatted_query, execute_arg = self._prepare(query, kwargs)
        async with self._connection.lock("query: %r" % pretty(query), self._token):
            self._connection.check_query(self, query)
            with self._connection.record_statement(query) as set_rows:
                await self._low_level.execute(formatted_query, execute_arg)
                result_set = ResultSet[SQLRow](self._low_level)
                await result_set.prepare()
                set_rows(result_set)
            try:
                yield result_set
            finally:
                result_set.detach()


class TransactionCursor(BasicCursor):
    def __init__(
        self,
        transaction: Transaction,
        connection: Connection,
        low_level: LowLevelCursor,
    ) -> None:
        super().__init__(connection, low_level)
        self.__transaction = transaction

    @property
    def transaction(self) -> Transaction:
        return self.__transaction

    @contextlib.asynccontextmanager
    async def query(
        self,
        query: str,
        *,
        for_update: bool = False,
        returning: Optional[str] = None,
        **kwargs: Parameter,
    ) -> AsyncIterator[ResultSet[SQLRow]]:
        if self._low_level is None:
            raise Exception("Closed cursor used.")
        formatted_query, execute_arg = self._prepare(
            query, kwargs, for_update=for_update, returning=returning
        )
        async with self._connection.lock("query: %r" % pretty(query), self._token):
            self._connection.check_query(self, query, for_update, returning)
            with self._connection.record_statement(query) as set_rows:
                await self._low_level.execute(formatted_query, execute_arg)
                result_set = ResultSet[SQLRow](self._low_level)
                await result_set.prepare()
                set_rows(result_set)
            try:
                yield result_set
            finally:
                result_set.detach()

    async def execute(self, statement: str, **kwargs: Parameter) -> None:
        if self._low_level is None:
            raise Exception("Closed cursor used.")
        formatted_statement, execute_arg = self._prepare(statement, kwargs)
        async with self._connection.lock(
            "statement: %r" % pretty(statement), self._token
        ):
            self._connection.check_statement(self, statement)
            with self._connection.record_statement(statement) as set_rows:
                await self._low_level.execute(formatted_statement, execute_arg)
                set_rows(self._low_level.rowcount)

    async def executemany(self, statement: str, values: Iterable[Parameters]) -> None:
        if self._low_level is None:
            raise Exception("Closed cursor used.")
        values = list(values)
        async with self._connection.lock(
            "statement+: %r" % pretty(statement), self._token
        ):
            self._connection.check_statement(self, statement)
            for kwargs in values:
                formatted_statement, execute_arg = self._prepare(statement, kwargs)
                with self._connection.record_statement(statement) as set_rows:
                    await self._low_level.execute(formatted_statement, execute_arg)
                    set_rows(self._low_level.rowcount)

    def _insert_statement(self, table_name: str, column_names: Sequence[str]) -> str:
        columns = ", ".join(f'"{name}"' for name in column_names)
        exprs = ", ".join(("{%s}" % name) for name in column_names)
        return f'INSERT INTO "{table_name}" ({columns}) VALUES ({exprs})'

    @overload
    async def insert(
        self,
        table_name: str,
        columns: Mapping[str, Parameter],
        *,
        returning: str,
        value_type: Type[ValueType],
    ) -> ValueType:
        ...

    @overload
    async def insert(self, table_name: str, columns: Mapping[str, Parameter]) -> None:
        ...

    async def insert(
        self,
        table_name: str,
        columns: Mapping[str, Parameter],
        *,
        returning: Optional[str] = None,
        value_type: Optional[Type[ValueType]] = None,
    ) -> Optional[ValueType]:
        statement = self._insert_statement(table_name, list(columns.keys()))
        if returning is not None:
            async with self.query(statement, returning=returning, **columns) as result:
                return cast(ValueType, await result.scalar())
        await self.execute(statement, **columns)
        return None

    async def insertmany(self, table_name: str, rows: Iterable[Parameters]) -> None:
        rows = iter(rows)
        try:
            row = next(rows)
        except StopIteration:
            return
        await self.executemany(
            self._insert_statement(table_name, list(row.keys())), [row, *rows]
        )

    async def delete(self, table_name: str, **where: Parameter) -> None:
        assert where
        conditions = [('"%s"={%s}' % (name, name)) for name in where.keys()]
        await self.execute(
            f'DELETE FROM "{table_name}" WHERE {" AND ".join(conditions)}', **where
        )


class CommitCallbacksFailed(Exception):
    pass


class SavepointError(Exception):
    pass


class Savepoint:
    release: bool

    def __init__(self, name: str):
        self.name = name
        self.release = False


class Transaction(AsyncContextManager[TransactionCursor]):
    __state: Literal["created", "active", "commit", "rollback"]
    __cursor: Optional[TransactionCursor]
    __future: "asyncio.Future[bool]"
    __commit_callbacks: List[Callable[[], Awaitable[None]]]
    __rollback_callbacks: List[Callable[[], Awaitable[None]]]
    __savepoints: Set[str]

    def __init__(
        self,
        connection: Connection,
        low_level: LowLevelConnection,
        start: Callable[[], Coroutine[Any, Any, None]],
        done: Callable[[], None],
    ) -> None:
        self.__connection = connection
        self.__low_level = low_level
        self.__state = "created"
        self.__start = start
        self.__done = done
        self.__started = False
        self.__task = asyncio.current_task()
        self.__cursor = None
        self.__future = asyncio.Future()
        self.__commit_callbacks = []
        self.__rollback_callbacks = []
        self.__savepoints = set()

    @property
    def started(self) -> bool:
        return self.__started

    @property
    def cursor(self) -> TransactionCursor:
        assert self.is_allowed_task()
        assert self.__cursor
        return self.__cursor

    def add_commit_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        assert self.__state in ("created", "active")
        self.__commit_callbacks.append(callback)

    def add_rollback_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        assert self.__state in ("created", "active")
        self.__rollback_callbacks.append(callback)

    @contextlib.asynccontextmanager
    async def savepoint(self, name: str) -> AsyncIterator[Savepoint]:
        if name in self.__savepoints:
            raise SavepointError(f"SAVEPOINT already in effect: {name}")
        self.__savepoints.add(name)
        await self.__low_level.savepoint(name)
        savepoint = Savepoint(name)
        try:
            yield savepoint
        except Exception:
            savepoint.release = False
            raise
        finally:
            self.__savepoints.remove(name)
            if savepoint.release:
                await self.__low_level.release_savepoint(name)
            else:
                await self.__low_level.rollback_to_savepoint(name)

    async def __aenter__(self) -> TransactionCursor:
        async with self.__connection.lock("transaction begin"):
            await self.__start()
            await self.__low_level.begin()
        self.__state = "active"
        self.__cursor = TransactionCursor(
            self, self.__connection, self.__low_level.cursor
        )
        self.__started = True
        return self.__cursor

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        async def signal_callbacks(
            callbacks: Collection[Callable[[], Awaitable[None]]]
        ) -> bool:
            failed = False
            for callback in callbacks:
                try:
                    await callback()
                except Exception as error:
                    logger.exception(
                        f"transaction post commit callback failed: {error}"
                    )
                    failed = True
            return not failed

        async def commit() -> None:
            await self.__low_level.commit()
            self.__state = "commit"

        async def rollback() -> None:
            await self.__low_level.rollback()
            self.__state = "rollback"

        try:
            async with self.__connection.lock("transaction end"):
                if exc_type is None:
                    try:
                        await commit()
                    except Exception:
                        await rollback()
                        raise
                else:
                    await rollback()
            if self.__state == "commit":
                if not await signal_callbacks(self.__commit_callbacks):
                    raise CommitCallbacksFailed()
        finally:
            if self.__state == "rollback":
                await signal_callbacks(self.__rollback_callbacks)
            self.__done()
            self.__future.set_result(True)

    def is_allowed_cursor(self, cursor: BasicCursor) -> bool:
        return cursor is self.__cursor

    def is_allowed_task(self) -> bool:
        return asyncio.current_task() is self.__task

    async def wait(self) -> None:
        await self.__future


class NoDefault:
    pass


FETCH_EAGERLY = False


RowType = TypeVar("RowType")
ValueType = TypeVar("ValueType")


class ResultSet(AsyncIterable[RowType]):
    ZeroRowsInResult = ZeroRowsInResult
    MultipleRowsInResult = MultipleRowsInResult
    MultipleColumnsInResult = MultipleColumnsInResult

    __cursor: Optional[LowLevelCursor]
    __rows: Optional[List[RowType]]

    def __init__(self, cursor: LowLevelCursor) -> None:
        self.__cursor = cursor
        self.__rows = None

    async def prepare(self) -> None:
        assert self.__cursor
        if FETCH_EAGERLY:
            self.__rows = list(cast(Iterable[RowType], await self.__cursor.fetchall()))
        self.__index = 0

    def count(self) -> int:
        assert self.__rows is not None
        return len(self.__rows)

    def detach(self) -> None:
        if self.__cursor:
            self.__cursor = None

    async def all(self) -> Sequence[RowType]:
        if not self.__cursor:
            raise DetachedResultSet()
        if self.__rows is not None:
            return self.__rows
        return cast(Sequence[RowType], await self.__cursor.fetchall())

    async def one(self) -> RowType:
        if not self.__cursor:
            raise DetachedResultSet()
        if self.__rows is None:
            row = cast(RowType, await self.__cursor.fetchone())
            if row is None:
                raise ZeroRowsInResult()
            if await self.__cursor.fetchall():
                raise MultipleRowsInResult()
            return row
        else:
            if not self.__rows:
                raise ZeroRowsInResult()
            if len(self.__rows) > 1:
                raise MultipleRowsInResult()
            return self.__rows[0]

    async def maybe_one(self) -> Optional[RowType]:
        try:
            return await self.one()
        except ZeroRowsInResult:
            return None

    async def scalar(self, *, default: Any = NoDefault) -> RowType:
        try:
            row = cast(Tuple[Any, ...], await self.one())
        except ZeroRowsInResult:
            if default is NoDefault:
                raise
            return default
        if len(row) > 1:
            raise MultipleColumnsInResult()
        return row[0]

    async def maybe_scalar(self) -> Optional[RowType]:
        return await self.scalar(default=None)

    async def scalars(self) -> Sequence[RowType]:
        rows = cast(Sequence[Tuple[RowType]], await self.all())
        if not rows:
            return []
        if len(rows[0]) > 1:
            raise MultipleColumnsInResult()
        return [scalar for (scalar,) in rows]

    async def ignore(self) -> None:
        # FIXME: Try to make this more efficient.
        await self.all()

    async def empty(self) -> bool:
        try:
            await self.one()
        except ZeroRowsInResult:
            return True
        await self.ignore()
        return False

    def __aiter__(self) -> AsyncIterator[RowType]:
        return self

    async def __anext__(self) -> RowType:
        if not self.__cursor:
            raise DetachedResultSet()
        row: RowType
        if self.__rows is None:
            row = cast(RowType, await self.__cursor.fetchone())
            if row is None:
                raise StopAsyncIteration
        else:
            if self.__index == len(self.__rows):
                raise StopAsyncIteration
            row = self.__rows[self.__index]
            self.__index += 1
        return row


class Query(AsyncContextManager[ResultSet[RowType]]):
    # inner: AsyncContextManager[ResultSet[RowType]]

    def __init__(
        self, cursor: BasicCursor, query: str, **parameters: Parameter
    ) -> None:
        self.inner = cursor.query(query, **parameters)

    async def __aenter__(self) -> ResultSet[RowType]:
        return cast(ResultSet[RowType], await self.inner.__aenter__())

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[Any],
    ) -> Any:
        return await self.inner.__aexit__(exc_type, exc, tb)


ScalarType = TypeVar("ScalarType", bound=SQLValue)


class Insert(Awaitable[ScalarType]):
    def __init__(
        self,
        cursor: TransactionCursor,
        table_name: str,
        columns: Mapping[str, Parameter],
        *,
        returning: str,
        value_type: Type[ScalarType],
    ):
        self.inner = cursor.insert(
            table_name, columns, returning=returning, value_type=value_type
        )

    def __await__(self) -> Generator[Any, None, ScalarType]:
        return cast(Generator[Any, None, ScalarType], self.inner.__await__())


from .postgresql import (
    IntegrityError,
    OperationalError,
    ProgrammingError,
    TransactionRollbackError,
    create_pool,
    create_formatter,
)


async def setup() -> Tuple[LowLevelConnectionPool, StatementFormatter]:
    global _pool, _formatter
    if _pool is None or _formatter is None:
        configuration = base.configuration()
        _pool = await create_pool(configuration)
        _formatter = await create_formatter(configuration)
    return _pool, _formatter


@contextlib.asynccontextmanager
async def connection() -> AsyncIterator[Connection]:
    pool, formatter = await setup()

    async with pool.acquire() as low_level:
        yield Connection(low_level, formatter)


async def shutdown() -> None:
    global _pool
    if _pool is not None:
        _pool.terminate()
        await _pool.wait_closed()
        _pool = None


__all__ = [
    "Adaptable",
    "adapt",
    "parameters",
    "IntegrityError",
    "OperationalError",
    "ProgrammingError",
    "TransactionRollbackError",
]
