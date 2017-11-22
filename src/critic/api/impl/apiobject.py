# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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
import functools
import logging
from typing import (
    Type,
    TypeVar,
    Iterable,
    AsyncIterable,
    AsyncIterator,
    Union,
    Tuple,
    Any,
    Generic,
    List,
    Optional,
    Mapping,
    Callable,
    Coroutine,
    Dict,
    Set,
    Protocol,
    Sequence,
    cast,
)

logger = logging.getLogger(__name__)

from .critic import NoKey
from critic import api
from critic import base
from critic import dbaccess


WrapperType = TypeVar("WrapperType", bound=api.APIObject)
ArgumentsType = TypeVar("ArgumentsType")
CacheKeyType = TypeVar("CacheKeyType")
T = TypeVar("T")
Fetch = TypeVar("Fetch", bound=Callable[..., Coroutine])
FetchMany = TypeVar("FetchMany", bound=Callable[..., Coroutine[Any, Any, Sequence]])


class InvalidIdError(Protocol):
    def __init__(self, *, invalid_id: Any) -> None:
        ...


class InvalidIdsError(Protocol):
    def __init__(self, *, invalid_ids: Iterable[Any]) -> None:
        ...


class APIObject(Generic[WrapperType, ArgumentsType, CacheKeyType]):
    ImplType = TypeVar("ImplType", bound="APIObject")

    wrapper_class: Type[WrapperType]
    table_name: Optional[str] = None
    column_names: Optional[List[str]] = None
    id_column = "id"

    def __init__(self, args: ArgumentsType) -> None:
        pass

    @classmethod
    @contextlib.asynccontextmanager
    async def query(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        query_or_conditions: Union[str, Iterable[str]] = [],
        /,
        *,
        order_by: Optional[str] = "",
        joins: Sequence[str] = None,
        **parameters: dbaccess.Parameter,
    ) -> AsyncIterator[dbaccess.ResultSet[ArgumentsType]]:
        if isinstance(query_or_conditions, str):
            query = query_or_conditions
        else:
            query = Implementation.default_query(
                *query_or_conditions, order_by=order_by, joins=joins
            )
        async with api.critic.Query[ArgumentsType](
            critic, query, **parameters
        ) as result:
            yield result

    @classmethod
    def table(Implementation: Type[ImplType]) -> str:
        if Implementation.table_name:
            return Implementation.table_name
        return Implementation.__name__.lower() + "s"

    @classmethod
    def columns(Implementation: Type[ImplType]) -> str:
        assert Implementation.column_names
        table_name = Implementation.table()
        return ", ".join(
            column_name if "." in column_name else f"{table_name}.{column_name}"
            for column_name in getattr(Implementation, "column_names")
        )

    @classmethod
    def primary_key(Implementation: Type[ImplType]) -> str:
        return f"{Implementation.table()}.{Implementation.id_column}"

    @classmethod
    def default_order_by(Implementation: Type[ImplType]) -> str:
        return f"{Implementation.primary_key()} ASC"

    @classmethod
    def default_joins(Implementation: Type[ImplType]) -> Sequence[str]:
        return []

    @staticmethod
    def order_by_clause(order_by: Optional[str]) -> str:
        return f" ORDER BY {order_by} " if order_by else " "

    @classmethod
    def default_query(
        Implementation: Type[ImplType],
        *conditions: str,
        order_by: Optional[str] = "",
        joins: Sequence[str] = None,
    ) -> str:
        assert Implementation.column_names
        if order_by == "":
            order_by = Implementation.default_order_by()
        if joins is None:
            joins = Implementation.default_joins()
        if joins:
            joins = ["", *joins]
        return f"""SELECT {Implementation.columns()}
                     FROM {Implementation.table()}
                  {' JOIN '.join(joins)}
                    WHERE {' AND '.join(["TRUE", *(f"({condition})" for condition in conditions)])}
                          {Implementation.order_by_clause(order_by)}"""

    @staticmethod
    def cacheKey(wrapper: WrapperType) -> CacheKeyType:
        return getattr(wrapper, "id")

    def wrap(self, critic: api.critic.Critic) -> WrapperType:
        return self.wrapper_class(critic, self)

    @staticmethod
    async def checkAccess(wrapper: WrapperType) -> None:
        pass

    @staticmethod
    def getSliceClauses(critic: api.critic.Critic) -> str:
        clauses = []
        try:
            offset, count = critic.popSlice()
            if offset is not None:
                clauses.append("OFFSET %d" % offset)
            if count is not None:
                clauses.append("LIMIT %d" % count)
        except api.critic.NoSlice:
            pass
        return " ".join(clauses)

    @classmethod
    def create(
        Implementation: Type[ImplType], critic: api.critic.Critic, args: ArgumentsType
    ) -> WrapperType:
        return Implementation(args).wrap(critic)

    @classmethod
    def get_cached(
        Implementation: Type[ImplType], critic: api.critic.Critic, item_id: CacheKeyType
    ) -> WrapperType:
        return cast(WrapperType, critic._impl.lookupObject(Implementation, item_id))

    @classmethod
    def get_all_cached(
        Implementation: Type[ImplType], critic: api.critic.Critic
    ) -> Mapping[CacheKeyType, WrapperType]:
        return cast(
            Mapping[CacheKeyType, WrapperType],
            critic._impl.lookupObjects(Implementation),
        )

    @classmethod
    def add_cached(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        item_id: CacheKeyType,
        item: WrapperType,
    ) -> None:
        critic._impl.assignObjects(Implementation, item_id, item)

    @classmethod
    def get_cached_custom(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        key: Any,
        default: Any = None,
    ) -> Any:
        return critic._impl.lookupCustom(Implementation, key, default=default)

    @classmethod
    def set_cached_custom(
        Implementation: Type[ImplType], critic: api.critic.Critic, key: Any, value: Any
    ) -> None:
        critic._impl.assignCustom(Implementation, key, value)

    @staticmethod
    def makeCacheKey(args: ArgumentsType) -> CacheKeyType:
        if isinstance(args, tuple):
            return args[0]
        return cast(CacheKeyType, args)

    @classmethod
    async def makeOne(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        values: Union[dbaccess.ResultSet[ArgumentsType], ArgumentsType],
    ) -> WrapperType:
        if isinstance(values, dbaccess.ResultSet):
            args = await values.one()
        else:
            args = values
        item_id = Implementation.makeCacheKey(args)
        item: WrapperType
        try:
            item = Implementation.get_cached(critic, item_id)
        except KeyError:
            item = Implementation.create(critic, args)
            assert Implementation.cacheKey(item) == item_id
            Implementation.add_cached(critic, item_id, item)
        return item

    @classmethod
    async def maybeMakeOne(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        values: Union[dbaccess.ResultSet, ArgumentsType],
        ignored_errors: Tuple[Type[Exception], ...],
    ) -> Optional[WrapperType]:
        try:
            return await Implementation.makeOne(critic, values)
        except Exception as error:
            if isinstance(error, ignored_errors):
                return None
            raise

    @classmethod
    async def make(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        args_list: Union[Iterable[ArgumentsType], AsyncIterable[ArgumentsType]],
        *,
        ignored_errors: Tuple[Type[Exception], ...] = (),
    ) -> List[WrapperType]:
        make_one = Implementation.maybeMakeOne
        result = []
        if hasattr(args_list, "__aiter__"):
            async for args in cast(AsyncIterable[ArgumentsType], args_list):
                item = await make_one(critic, args, ignored_errors)
                if item is not None:
                    result.append(item)
        else:
            for args in cast(Iterable[ArgumentsType], args_list):
                item = await make_one(critic, args, ignored_errors)
                if item is not None:
                    result.append(item)
        return result

    @staticmethod
    def fetchCacheKey(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[api.critic.Critic, Optional[CacheKeyType]]:
        return critic, args[0]

    @classmethod
    def getInvalidIdError(Implementation: Type[ImplType]) -> Type[api.InvalidIdError]:
        if hasattr(Implementation, "invalid_id_error"):
            return getattr(Implementation, "invalid_id_error")
        return Implementation.wrapper_class.getModule().InvalidId

    @classmethod
    def cached(Implementation: Type[ImplType], fetch: Fetch) -> Fetch:
        @functools.wraps(fetch)
        async def wrapper(*args: Any) -> Any:
            critic, item_id = Implementation.fetchCacheKey(*args)
            assert isinstance(critic, api.critic.Critic)
            if item_id is not None:
                try:
                    return critic._impl.lookupObject(Implementation, item_id)
                except KeyError:
                    pass
            try:
                return await fetch(*args)
            except dbaccess.ZeroRowsInResult:
                if item_id is None:
                    raise

                InvalidId = Implementation.getInvalidIdError()
                raise InvalidId(invalid_id=item_id) from None

        return cast(Fetch, wrapper)

    @staticmethod
    def fetchManyCacheKeys(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[
        api.critic.Critic, Optional[List[CacheKeyType]], Optional[Iterable[Any]]
    ]:
        return critic, args[0], None

    @classmethod
    def getInvalidIdsError(Implementation: Type[ImplType]) -> Type[api.InvalidIdsError]:
        return Implementation.wrapper_class.getModule().InvalidIds

    @classmethod
    def cachedMany(Implementation: Type[ImplType], fetchMany: FetchMany) -> FetchMany:
        @functools.wraps(fetchMany)
        async def wrapper(*args: Any) -> Sequence:
            (critic, item_ids, item_args) = Implementation.fetchManyCacheKeys(*args)
            assert isinstance(critic, api.critic.Critic)
            if item_ids is None:
                return await fetchMany(*args)
            cache: Mapping
            try:
                cache = critic._impl.lookupObjects(Implementation)
            except KeyError:
                cache = {}
            uncached_ids = set(item_ids) - set(cache.keys())
            items: Dict[Any, WrapperType] = {
                item_id: cache[item_id] for item_id in item_ids if item_id in cache
            }
            if uncached_ids:
                if item_args:
                    uncached_args = [
                        args
                        for item_id, args in zip(item_ids, item_args)
                        if item_id in uncached_ids
                    ]
                else:
                    uncached_args = list(uncached_ids)
                fetched = await fetchMany(critic, uncached_args)
                items.update((Implementation.cacheKey(item), item) for item in fetched)
            if len(items) < len(set(item_ids)):
                invalid_ids = sorted(set(item_ids) - set(items.keys()))

                # This cast is somewhat dubious: the assumption though is
                # that any sub-class that has an irregular cache key type
                # will also have an irregular fetch, not using this code
                # path.
                InvalidIds = Implementation.getInvalidIdsError()
                raise InvalidIds(invalid_ids=cast(List[int], invalid_ids))
            return [items[item_id] for item_id in item_ids]

        return cast(FetchMany, wrapper)

    @classmethod
    def allCached(
        Implementation: Type[ImplType], critic: api.critic.Critic,
    ) -> Mapping[Any, WrapperType]:
        """Return all cached objects of this type

           The cached objects are returned as a dictionary mapping the object id
           to the object. This dictionary should not be modified."""
        # Don't catch KeyError here. Something is probably wrong if this
        # function is called when no objects of the type are cached.
        return cast(
            Mapping[Any, WrapperType], critic._impl.lookupObjects(Implementation)
        )

    @classmethod
    def filteredCached(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        filterfn: Callable[[WrapperType], T],
    ) -> List[T]:
        """Return all cached objects of this type

           The cached objects are returned as a dictionary mapping the object id
           to the object. This dictionary should not be modified."""
        # Don't catch KeyError here. Something is probably wrong if this
        # function is called when no objects of the type are cached.
        return [
            value
            for value in map(filterfn, Implementation.allCached(critic))
            if value is not None
        ]

    @classmethod
    def refresh_tables(cls: Type[ImplType]) -> Iterable[str]:
        return {cls.table()}

    @classmethod
    async def refresh(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        tables: Set[str],
        cached_objects: Mapping[Any, WrapperType],
    ) -> None:
        """Refresh objects after transaction commit

           The |tables| parameter is a set of database tables that were modified
           in the transaction. The |cached_objects| parameter is a dictionary
           mapping object ids to cached objects (wrappers) of this type."""
        if not tables.intersection(Implementation.refresh_tables()):
            return
        await Implementation.updateAll(
            critic,
            [f"{Implementation.primary_key()}=ANY({{object_ids}})"],
            cached_objects,
        )

    @classmethod
    async def updateAll(
        Implementation: Type[ImplType],
        critic: api.critic.Critic,
        query_or_conditions: Union[str, Iterable[str]],
        cached_objects: Mapping[Any, WrapperType],
        **parameters: dbaccess.Parameter,
    ) -> None:
        """Execute the query and update all cached objects

           The query must take a single parameter, named `object_ids`, which is
           a list of object ids. It will be executed with the list of ids of all
           objects in `cached_objects`. Each returned row must have the id of
           the object as the first item, and the implementation constructor must
           take the row as a whole as arguments:

             new_impl = Implementation(*row)"""
        async with Implementation.query(
            critic, query_or_conditions, object_ids=list(cached_objects), **parameters
        ) as result:
            async for row in result:
                cached_objects[row[0]]._set_impl(Implementation(row))
