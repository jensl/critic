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

import aiopg
import contextlib
import logging
from psycopg2 import IntegrityError, OperationalError, ProgrammingError
from psycopg2.extensions import TransactionRollbackError
from typing import Any, Dict, Optional, Tuple, AsyncIterator, Protocol

logger = logging.getLogger(__name__)

from . import LowLevelConnection, LowLevelCursor, LowLevelConnectionPool
from .formatter import Parameters, ExecuteArguments, StatementFormatter
from critic import base


class Formatter(StatementFormatter):
    __cache: Dict[str, str]

    def __init__(self) -> None:
        self.__cache = {}

    def process(
        self, sql: str, parameters: Parameters, **kwargs: Dict[str, Any],
    ) -> Tuple[str, ExecuteArguments]:
        returning = kwargs.pop("returning", None)
        if returning is not None:
            sql += " RETURNING " + str(returning)
        for_update = kwargs.pop("for_update", False)
        if for_update:
            sql += " FOR UPDATE"
        if sql not in self.__cache:
            self.__cache[sql], _ = super().process(sql, parameters)
        return self.__cache[sql], parameters

    def replace(
        self,
        expr: Optional[str],
        parameter_name: str,
        mode: Optional[str],
        execute_args: Optional[ExecuteArguments],
        parameters: Parameters,
    ) -> Tuple[str, ExecuteArguments]:
        if mode == "eq":
            replacement = f"{parameter_name}=%({parameter_name})s"
        elif mode == "array":
            replacement = f"{expr or parameter_name}=ANY (%({parameter_name})s)"
        elif expr:
            replacement = f"{expr}=%({parameter_name})s"
        else:
            replacement = f"%({parameter_name})s"
        return replacement, parameters


class Connection(LowLevelConnection):
    def __init__(self, impl: Any, cursor: LowLevelCursor) -> None:
        self.__impl = impl
        self.__cursor = cursor

    @property
    def cursor(self) -> LowLevelCursor:
        return self.__cursor

    async def begin(self) -> None:
        await self.cursor.execute("BEGIN")

    async def commit(self) -> None:
        await self.cursor.execute("COMMIT")

    async def rollback(self) -> None:
        await self.cursor.execute("ROLLBACK")

    async def cancel(self) -> None:
        await self.__impl.cancel()

    async def close(self) -> None:
        self.__impl.close()


class Pool(LowLevelConnectionPool):
    def __init__(self, impl: Any) -> None:
        self.__impl = impl

    @contextlib.asynccontextmanager
    async def acquire(self) -> AsyncIterator[LowLevelConnection]:
        async with self.__impl.acquire() as connection:
            async with connection.cursor() as cursor:
                yield Connection(connection, cursor)

    def terminate(self) -> None:
        self.__impl.terminate()

    async def wait_closed(self) -> None:
        await self.__impl.wait_closed()


async def create_pool(configuration: base.Configuration) -> LowLevelConnectionPool:
    parameters = configuration["database.parameters"]
    assert isinstance(parameters, dict)
    args = parameters["args"]
    assert isinstance(args, list)
    kwargs = parameters["kwargs"]
    assert isinstance(kwargs, dict)
    return Pool(await aiopg.create_pool(*args, **kwargs))


async def create_formatter(configuration: base.Configuration) -> StatementFormatter:
    return Formatter()
