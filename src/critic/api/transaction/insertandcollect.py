# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from typing import (
    Awaitable,
    Collection,
    Generic,
    Callable,
    Optional,
    TypeVar,
    cast,
)

from critic import dbaccess
from .base import TransactionBase

IntermediateType = TypeVar("IntermediateType", bound=dbaccess.SQLValue)
FinalType = TypeVar("FinalType")


class InsertAndCollect(Generic[IntermediateType, FinalType]):
    __statement: Optional[str]
    __values: Optional[dbaccess.Parameters]

    def __init__(
        self,
        table_name: str,
        /,
        *,
        returning: str,
        collector: Optional[Callable[[IntermediateType], Awaitable[FinalType]]] = None,
    ):
        self.table_name = table_name
        self.__statement = None
        self.__values = None
        self.__returning = returning
        self.__collector = collector

    @property
    def table_names(self) -> Collection[str]:
        return (self.table_name,)

    async def __call__(
        self,
        transaction: TransactionBase,
        cursor: dbaccess.TransactionCursor,
    ) -> FinalType:
        assert self.__statement is not None
        assert self.__values is not None
        async with dbaccess.Query[IntermediateType](
            cursor, self.__statement, returning=self.__returning, **self.__values
        ) as result:
            intermediate = await result.scalar()
        if self.__collector:
            return await self.__collector(intermediate)
        return cast(FinalType, intermediate)

    def values(
        self, **values: dbaccess.Parameter
    ) -> InsertAndCollect[IntermediateType, FinalType]:
        column_names = sorted(values.keys())
        parameters = ["{%s}" % name for name in column_names]
        self.__statement = f"""
            INSERT
              INTO {self.table_name} ({", ".join(f'"{name}"' for name in column_names)})
            VALUES ({", ".join(parameters)})
        """
        self.__values = values
        return self
