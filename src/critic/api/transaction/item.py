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

import logging
import re
from abc import ABC, abstractmethod
from typing import (
    Collection,
    Generic,
    Protocol,
    Any,
    List,
    Callable,
    Set,
    Union,
    Optional,
    Sequence,
    Iterable,
    TypeVar,
    Dict,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from .base import TransactionBase


class Keyed(Protocol):
    @property
    def key(self) -> Any:
        ...


# class Item(Keyed, metaclass=abc.ABCMeta):
#     tables: FrozenSet[str] = frozenset()

#     def __hash__(self) -> int:
#         return hash(self.key)

#     def __eq__(self, other: object) -> bool:
#         return isinstance(other, type(self)) and self.key == other.key

#     @abc.abstractmethod
#     async def __call__(
#         self,
#         transaction: TransactionBase,
#         cursor: dbaccess.TransactionCursor,
#     ) -> None:
#         assert False, "Must be overridden by sub-class!"


# class Items:
#     __items: List[Item]

#     def __init__(self, transaction: TransactionBase):
#         self.__transaction = transaction
#         self.__items = []

#     def __bool__(self) -> bool:
#         return bool(self.__items)

#     def append(self, item: Item) -> None:
#         self.__transaction.tables.update(item.tables)
#         if self and isinstance(item, Query):
#             last = self.last()
#             if isinstance(last, Query) and last.merge(item):
#                 return
#         self.__items.append(item)

#     def last(self) -> Item:
#         return self.__items[-1]

#     def pop(self) -> Item:
#         return self.__items.pop(0)

#     def take(self) -> List[Item]:
#         items, self.__items = self.__items, []
#         return items


CollectorCallback = Callable[..., Any]
# Collector = Union[CollectorCallback, LazyValue, types.ModuleType]


class SubQuery:
    def __init__(self, query: str, **parameters: dbaccess.SQLValue):
        self.query = query
        self.parameters = parameters


class Query:
    _values: List[dbaccess.Parameters]

    def __init__(
        self,
        statement: Optional[str],
        *values: dbaccess.Parameters,
        # returning: Optional[str] = None,
        # collector: Optional[Collector] = None,
        **kwargs: dbaccess.Parameter,
    ):
        self.statement = statement
        # self.returning = returning
        # self.__collector = collector
        if values:
            self._values = list(values)
        else:
            self._values = [kwargs]
        # for values in self.values:
        #     for key, value in values.items():
        #         assert not asyncio.iscoroutine(value), key
        # assert all(isinstance(kwargs, dict) for kwargs in self.__values)

    def __repr__(self) -> str:
        import re

        if self.statement is None:
            return "Query(...)"
        return "Query(%r, %r)" % (
            re.sub(r"\s+", " ", self.statement),
            repr(self._values),
        )

    # def result_collector(
    #     self, transaction: TransactionBase
    # ) -> Optional[CollectorCallback]:
    #     if isinstance(self.__collector, (LazyInt, LazyObject)):
    #         return self.__collector
    #     if self.__collector is None:
    #         if self.returning is None:
    #             return None
    #         self.__collector = LazyInt()
    #     elif isinstance(self.__collector, types.ModuleType):
    #         # The collector is an API module.
    #         self.__collector = GenericLazyAPIObject(transaction, self.__collector)
    #     else:
    #         assert callable(self.__collector)
    #     return self.__collector

    # def merge(self, query: Query) -> bool:
    #     if (
    #         self.statement is not None
    #         and query.statement is not None
    #         and self.statement == query.statement
    #         and not self.__collector
    #         and not query.__collector
    #     ):
    #         self._values.extend(query._values)
    #         return True
    #     return False

    # @staticmethod
    # def evaluate(value: Any) -> dbaccess.Parameter:
    #     def inner(value):
    #         if isinstance(value, (set, frozenset, list, tuple)):
    #             return [inner(element) for element in value]
    #         if isinstance(value, dict):
    #             return {key: inner(item) for key, item in value.items()}
    #         if isinstance(value, api.APIObject):
    #             return value.id
    #         if isinstance(value, LazyValue):
    #             return int(value)
    #         return value

    #     return inner(value)

    # @property
    # def values(self): Iterator[Any]:
    #     for values in self.__values:
    #         yield self.evaluate(values)

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        assert self.statement is not None
        # collector = self.result_collector(transaction)
        # if collector:
        #     for values in self._values:
        #         async with cursor.query(
        #             self.statement, returning=self.returning, **values
        #         ) as result:
        #             async for row in result:
        #                 collector(*row)
        # else:
        await cursor.executemany(self.statement, self._values)


T = TypeVar("T", bound="_GeneratedQuery")


SQLValue = TypeVar("SQLValue", bound=dbaccess.SQLValue)


class _GeneratedQuery(ABC):
    parameters: Dict[str, dbaccess.Parameter]

    def __init__(self, table_or_object: Union[str, api.APIObject]):
        self.conditions: List[str] = []
        self.parameters = {}
        if isinstance(table_or_object, api.APIObject):
            self.table_name = table_or_object.getTableName()
            self.id_column = table_or_object.getIdColumn()
            self.where(**{self.id_column: table_or_object.id})
        else:
            self.table_name = str(table_or_object)
            self.id_column = "*"
        self.tables = frozenset({self.table_name})

    @property
    def table_names(self) -> Collection[str]:
        return (self.table_name,) if self.table_name else ()

    def set_parameter(self, name: str, value: dbaccess.Parameter) -> None:
        assert name not in self.parameters
        self.parameters[name] = value

    @overload
    def where(self: T, condition: str, /, **parameters: dbaccess.Parameter) -> T:
        ...

    @overload
    def where(self: T, **columns: Union[dbaccess.Parameter, SubQuery]) -> T:
        ...

    def where(  # type: ignore
        self: T,
        condition: Optional[str] = None,
        /,
        **columns: Union[dbaccess.Parameter, SubQuery],
    ) -> T:
        if condition is not None:
            self.conditions.append(condition)
            for name, value in columns.items():
                assert name not in self.parameters and not isinstance(value, SubQuery)
                self.set_parameter(name, value)
        else:
            for name, value in sorted(columns.items()):
                if isinstance(value, SubQuery):
                    self.conditions.append(f"{name} IN ({value.query})")
                    for subquery_name, value in value.parameters.items():
                        self.set_parameter(subquery_name, value)
                else:
                    self.set_parameter(f"where_{name}", value)
                    if isinstance(value, (list, tuple)):
                        self.conditions.append("%s=ANY ({where_%s})" % (name, name))
                    else:
                        self.conditions.append("%s={where_%s}" % (name, name))
        return self

    async def execute(self, cursor: dbaccess.TransactionCursor) -> None:
        statement = self.statement
        if statement:
            await cursor.execute(statement, **self.parameters)

    @property
    @abstractmethod
    def statement(self) -> Optional[str]:
        pass


class Insert(_GeneratedQuery):
    __query: Optional[str]

    def __init__(self, table_name: str) -> None:
        super().__init__(table_name)
        self.__default_values = False
        self.__query = None

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        await self.execute(cursor)

    def _set_column_names(self, column_names: Sequence[str]) -> None:
        self.__column_names = column_names
        self.__value_names = ["{%s}" % name for name in column_names]

    def columns(self, *column_names: str) -> Insert:
        self._set_column_names(column_names)
        return self

    def values(self, **columns: dbaccess.Parameter) -> Insert:
        self._set_column_names(sorted(columns.keys()))
        self.parameters.update(columns)
        return self

    def default_values(self) -> Insert:
        self.__default_values = True
        return self

    def query(self, query: str, **parameters: dbaccess.SQLValue) -> Insert:
        self.__query = query
        for name, value in parameters.items():
            self.set_parameter(name, value)
        return self

    @property
    def statement(self) -> str:
        if self.__default_values:
            values = "DEFEULT VALUES"
        elif self.__query:
            values = self.__query
        else:
            values = f"VALUES ({', '.join(self.__value_names)})"
        return f"""
            INSERT INTO {self.table_name} ({", ".join(self.__column_names)})
            {values}
        """


class InsertMany(Insert):
    def __init__(
        self,
        table_name: str,
        column_names: Sequence[str],
        values: Iterable[dbaccess.Parameters],
    ):
        super().__init__(table_name)
        self._set_column_names(column_names)
        self.__values = values

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        await cursor.executemany(self.statement, self.__values)


class Update(_GeneratedQuery):
    columns: Set[str]

    def __init__(self, table_or_object: Union[str, api.APIObject]):
        super().__init__(table_or_object)
        self.columns = set()

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        statement = self.statement
        assert statement
        logger.debug("%s %r", re.sub(r"\s+", " ", statement), self.parameters)
        await self.execute(cursor)

    def _set_updates(self, column_names: Sequence[str]) -> None:
        self.columns.update(column_names)

    def set(self, **columns: dbaccess.Parameter) -> Update:
        self._set_updates(sorted(columns.keys()))
        for name, value in columns.items():
            self.set_parameter(f"set_{name}", value)
        return self

    def set_if(self, **columns: dbaccess.Parameter) -> Update:
        return self.set(
            **{name: value for name, value in columns.items() if value is not None}
        )

    @property
    def statement(self) -> Optional[str]:
        if not self.columns:
            return None
        return f"""
            UPDATE {self.table_name}
               SET {", ".join(("%s={set_%s}" % (name, name)) for name in sorted(self.columns))}
             WHERE {" AND ".join(self.conditions)}
        """


class UpdateMany(Update):
    def __init__(
        self,
        table_name: str,
        column_names: Sequence[str],
        values: Iterable[dbaccess.Parameters],
    ):
        super().__init__(table_name)
        self._set_updates(column_names)
        self.__values = values

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        statement = self.statement
        if statement:
            await cursor.executemany(statement, self.__values)


class Delete(_GeneratedQuery):
    @property
    def statement(self) -> str:
        return f"""
            DELETE
              FROM {self.table_name}
             WHERE {" AND ".join(self.conditions)}
        """

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        await self.execute(cursor)


class Verify(_GeneratedQuery):
    column_names: List[str]
    expected_values: Dict[str, dbaccess.Parameter]

    def __init__(self, table_or_object: Union[str, api.APIObject]):
        super().__init__(table_or_object)
        self.column_names = []
        self.expected_values = {}

    def that(self, **checks: dbaccess.Parameter) -> Verify:
        for column_name, value in checks.items():
            self.column_names.append(column_name)
            self.expected_values[column_name] = value
        return self

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        async with cursor.query(self.statement, **self.parameters) as result:
            async for row in result:
                for column_name, actual_value in zip(self.column_names, row):
                    expected_value = self.expected_values[column_name]
                    if dbaccess.adapt(expected_value) != actual_value:
                        raise api.TransactionError(
                            f"check failed: {column_name}: "
                            f"expected {expected_value!r}, "
                            f"got {actual_value!r}"
                        )

    @property
    def statement(self) -> str:
        return f"""SELECT {", ".join(self.column_names)}
                  FROM {self.table_name}
                 WHERE {" AND ".join(self.conditions)}"""


RowType = TypeVar("RowType", contravariant=True)


class CheckCallback(Protocol[RowType]):
    async def __call__(self, result: RowType) -> None:
        ...


class Check(Generic[RowType]):
    callbacks: List[CheckCallback[RowType]]

    def __init__(self, statement: str, **parameters: dbaccess.Parameter):
        self.statement = statement
        self.parameters = parameters
        self.callbacks = []

    @property
    def table_names(self) -> Collection[str]:
        return ()

    def that(self, callback: CheckCallback[RowType]) -> Check[RowType]:
        self.callbacks.append(callback)
        return self

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        async with dbaccess.Query[RowType](
            cursor, self.statement, **self.parameters
        ) as result:
            async for row in result:
                for callback in self.callbacks:
                    await callback(row)


class Lock(_GeneratedQuery):
    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> None:
        async with cursor.query(
            self.statement, **self.parameters, for_update=True
        ) as result:
            await result.ignore()

    @property
    def statement(self) -> Optional[str]:
        return f"""
            SELECT FOR UPDATE {self.id_column}
              FROM {self.table_name}
             WHERE {" AND ".join(self.conditions)}
        """


class FetchBase(_GeneratedQuery):
    def __init__(self, table_name: str, *expressions: str):
        super().__init__(table_name)
        self.__expressions = expressions

    @property
    def statement(self) -> Optional[str]:
        return f"""
            SELECT {", ".join(self.__expressions)}
              FROM {self.table_name}
             WHERE {" AND ".join(self.conditions)}
        """


class Fetch(FetchBase, Generic[SQLValue]):
    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> SQLValue:
        statement = self.statement
        assert statement
        async with dbaccess.Query[SQLValue](
            cursor, statement, **self.parameters
        ) as result:
            return await result.scalar()


class FetchAll(FetchBase, Generic[RowType]):
    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> Sequence[RowType]:
        statement = self.statement
        assert statement
        async with dbaccess.Query[RowType](
            cursor, statement, **self.parameters
        ) as result:
            return await result.all()


ScalarType = TypeVar("ScalarType")


class FetchScalars(FetchBase, Generic[ScalarType]):
    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> Sequence[ScalarType]:
        statement = self.statement
        assert statement
        async with dbaccess.Query[ScalarType](
            cursor, statement, **self.parameters
        ) as result:
            return await result.scalars()
