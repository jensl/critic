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

import abc
import types
from typing import (
    FrozenSet,
    Protocol,
    Any,
    List,
    Callable,
    Union,
    Optional,
    Sequence,
    Iterable,
    TypeVar,
    Dict,
    cast,
)

from .lazy import LazyInt, LazyValue, LazyObject, LazyAPIObject, GenericLazyAPIObject
from critic import api
from critic import dbaccess


class Keyed(Protocol):
    @property
    def key(self) -> Any:
        ...


class Item(Keyed, metaclass=abc.ABCMeta):
    tables: FrozenSet[str] = frozenset()

    def __hash__(self) -> int:
        return hash(self.key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self.key == other.key

    @abc.abstractmethod
    async def __call__(
        self,
        transaction: api.transaction.Transaction,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        assert False, "Must be overridden by sub-class!"


class Items:
    __items: List[Item]

    def __init__(self, transaction: api.transaction.Transaction):
        self.__transaction = transaction
        self.__items = []

    def __bool__(self) -> bool:
        return bool(self.__items)

    def append(self, item: Item) -> None:
        self.__transaction.tables.update(item.tables)
        if self and isinstance(item, Query):
            last = self.last()
            if isinstance(last, Query) and last.merge(item):
                return
        self.__items.append(item)

    def last(self) -> Item:
        return self.__items[-1]

    def pop(self) -> Item:
        return self.__items.pop(0)

    def take(self) -> List[Item]:
        items, self.__items = self.__items, []
        return items


CollectorCallback = Callable[..., Any]
Collector = Union[CollectorCallback, LazyValue, types.ModuleType]


class Query(Item):
    _values: List[dbaccess.Parameters]

    def __init__(
        self,
        statement: Optional[str],
        *values: dbaccess.Parameters,
        returning: str = None,
        collector: Collector = None,
        **kwargs: dbaccess.Parameter,
    ):
        self.statement = statement
        self.returning = returning
        self.__collector = collector
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

    def result_collector(
        self, transaction: api.transaction.Transaction
    ) -> Optional[CollectorCallback]:
        if isinstance(self.__collector, (LazyInt, LazyObject)):
            return self.__collector
        if self.__collector is None:
            if self.returning is None:
                return None
            self.__collector = LazyInt()
        elif isinstance(self.__collector, types.ModuleType):
            # The collector is an API module.
            self.__collector = GenericLazyAPIObject(transaction, self.__collector)
        else:
            assert callable(self.__collector)
        return self.__collector

    def merge(self, query: Query) -> bool:
        if (
            self.statement is not None
            and query.statement is not None
            and self.statement == query.statement
            and not self.__collector
            and not query.__collector
        ):
            self._values.extend(query._values)
            return True
        return False

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
        self,
        transaction: api.transaction.Transaction,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        assert self.statement is not None
        collector = self.result_collector(transaction)
        if collector:
            for values in self._values:
                async with cursor.query(
                    self.statement, returning=self.returning, **values
                ) as result:
                    async for row in result:
                        collector(*row)
        else:
            await cursor.executemany(self.statement, self._values)


class Insert(Query, Item):
    def __init__(
        self, table_name: str, /, *, returning: str = None, collector: Collector = None,
    ) -> None:
        Query.__init__(self, None, returning=returning, collector=collector)
        self.table_name = table_name
        self.tables = frozenset({table_name})

    def values(self, **columns: dbaccess.Parameter) -> Insert:
        column_names = sorted(columns.keys())
        parameters = ["{%s}" % name for name in column_names]
        self.statement = f"""INSERT
                               INTO {self.table_name} ({", ".join(column_names)})
                             VALUES ({", ".join(parameters)})"""
        self._values = [columns]
        return self


class InsertMany(Query, Item):
    def __init__(
        self,
        table_name: str,
        column_names: Sequence[str],
        values: Iterable[dbaccess.Parameters],
        returning: str = None,
        collector: Collector = None,
    ):
        self.tables = frozenset({table_name})
        assert values
        parameters = ["{%s}" % name for name in column_names]
        statement = f"""INSERT
                          INTO {table_name} ({", ".join(column_names)})
                        VALUES ({", ".join(parameters)})"""
        Query.__init__(
            self, statement, *values, returning=returning, collector=collector
        )


T = TypeVar("T", bound="_GeneratedQuery")


class _GeneratedQuery(Query, Item):
    parameters: Dict[str, dbaccess.Parameter]

    def __init__(self, table_or_object: Union[str, api.APIObject, LazyAPIObject]):
        self.conditions: List[str] = []
        self.parameters = {}
        Query.__init__(self, None, self.parameters)
        if isinstance(table_or_object, (api.APIObject, LazyAPIObject)):
            if isinstance(table_or_object, api.APIObject):
                self.table_name = table_or_object._impl.table()
                id_column = table_or_object._impl.id_column
            else:
                self.table_name = table_or_object.table_name
                id_column = table_or_object.id_column
            self.where(**{id_column: table_or_object.id})
        else:
            self.table_name = str(table_or_object)
        self.tables = frozenset({self.table_name})

    def where(self: T, **columns: dbaccess.Parameter) -> T:
        for name, value in sorted(columns.items()):
            assert name not in self.parameters
            mode = ""
            if not isinstance(value, str):
                try:
                    value = list(cast(Iterable[Any], value))
                except TypeError:
                    pass
                else:
                    mode = ":array"
            self.conditions.append("{%s=%s%s}" % (name, name, mode))
            self.parameters[name] = value
        return self

    async def __call__(
        self,
        transaction: api.transaction.Transaction,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        self.set_statement()
        await super().__call__(transaction, cursor)

    def set_statement(self) -> None:
        pass


class Update(_GeneratedQuery):
    updates: List[str]

    def __init__(self, table_or_object: Union[str, api.APIObject, LazyAPIObject]):
        super().__init__(table_or_object)
        self.updates = []

    def set(self, **columns: dbaccess.Parameter) -> Update:
        for name, value in sorted(columns.items()):
            assert name not in self.parameters
            self.updates.append("%s={%s}" % (name, name))
            self.parameters[name] = value
        return self

    def set_statement(self) -> None:
        self.statement = f"""UPDATE {self.table_name}
                                SET {", ".join(self.updates)}
                              WHERE {" AND ".join(self.conditions)}"""


class Delete(_GeneratedQuery):
    def set_statement(self) -> None:
        self.statement = f"""DELETE
                               FROM {self.table_name}
                              WHERE {" AND ".join(self.conditions)}"""


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
        self,
        transaction: api.transaction.Transaction,
        cursor: dbaccess.TransactionCursor,
    ) -> None:
        async with cursor.query(
            f"""SELECT {", ".join(self.column_names)}
                  FROM {self.table_name}
                 WHERE {" AND ".join(self.conditions)}""",
            **self.parameters,
        ) as result:
            async for row in result:
                for column_name, actual_value in zip(self.column_names, row):
                    expected_value = self.expected_values[column_name]
                    if dbaccess.adapt(expected_value) != actual_value:
                        raise api.TransactionError(
                            f"check failed: {column_name}: "
                            f"expected {expected_value!r}, "
                            f"got {actual_value!r}"
                        )
