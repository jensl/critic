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

from abc import abstractmethod
import logging
import types
from typing import (
    Awaitable,
    ClassVar,
    Collection,
    Dict,
    FrozenSet,
    Type,
    TypeVar,
    Iterable,
    Tuple,
    Any,
    Optional,
    Mapping,
    Callable,
    Coroutine,
    Protocol,
    Sequence,
    cast,
)


logger = logging.getLogger(__name__)

from critic import api
from .objectcache import (
    InvalidCacheKey,
    InvalidCacheKeys,
    KeyType,
    ObjectCache,
)
from .queryhelper import (
    QueryResult,
    ValueExceptionFactory,
    ValuesExceptionFactory,
)


PublicType = TypeVar("PublicType", bound=api.APIObject)
ArgumentsType = TypeVar("ArgumentsType", bound=Tuple[object, ...])
CacheKeyType = TypeVar("CacheKeyType")
T = TypeVar("T")
Fetch = TypeVar("Fetch", bound=Callable[..., Coroutine[Any, Any, Any]])
FetchMany = TypeVar(
    "FetchMany", bound=Callable[..., Coroutine[Any, Any, Sequence[Any]]]
)


class InvalidIdError(Protocol):
    def __init__(self, *, invalid_id: Any) -> None:
        ...


class InvalidIdsError(Protocol):
    def __init__(self, *, invalid_ids: Iterable[Any]) -> None:
        ...


ActualAPIObjectImpl = TypeVar("ActualAPIObjectImpl", bound="APIObjectImpl")


class APIObjectImpl(
    api.APIObject,
):
    __module: ClassVar[types.ModuleType]

    def __init_subclass__(cls, *, module: Optional[types.ModuleType] = None):
        if module is not None:
            cls.setModule(module)
        ObjectCache.registerRefresher(cls.getCacheCategory(), cls.refreshAll)

    def __init__(self, critic: api.critic.Critic) -> None:
        self.__critic = critic

    @property
    def critic(self) -> api.critic.Critic:
        return self.__critic

    @classmethod
    def getModule(cls) -> types.ModuleType:
        return cls.__module

    @classmethod
    def setModule(cls, module: types.ModuleType) -> None:
        cls.__module = module

    @classmethod
    def getCacheCategory(cls) -> str:
        return cls.__name__

    @abstractmethod
    def getCacheKeys(self) -> Collection[object]:
        ...

    @classmethod
    def allCached(
        cls: Type[ActualAPIObjectImpl],
    ) -> Mapping[object, ActualAPIObjectImpl]:
        """Return all cached objects of this type

        The cached objects are returned as a dictionary mapping the object id
        to the object. This dictionary should not be modified."""
        # Don't catch KeyError here. Something is probably wrong if this
        # function is called when no objects of the type are cached.
        return ObjectCache.get().findAll(cls.getCacheCategory(), cls)

    @classmethod
    def refresh_tables(cls) -> Iterable[str]:
        return {cls.getTableName()}

    @classmethod
    async def refreshAll(
        cls,
        critic: api.critic.Critic,
        tables: Optional[FrozenSet[str]],
        cached_objects: Collection[object],
    ) -> None:
        """Refresh objects after transaction commit

        The |tables| parameter is a set of database tables that were modified
        in the transaction. The |cached_objects| parameter is a dictionary
        mapping object ids to cached objects (wrappers) of this type."""
        if tables and not tables.intersection(cls.refresh_tables()):
            return
        await cls.doRefreshAll(critic, cached_objects)

    @classmethod
    async def doRefreshAll(
        cls,
        critic: api.critic.Critic,
        cached_objects: Collection[object],
        /,
    ) -> None:
        pass

    @classmethod
    def getInvalidIdError(cls) -> ValueExceptionFactory:
        if hasattr(cls, "invalid_id_error"):
            return getattr(cls, "invalid_id_error")
        return getattr(cls.getModule(), "InvalidId")

    @classmethod
    def getInvalidIdsError(cls) -> ValuesExceptionFactory:
        if hasattr(cls, "invalid_ids_error"):
            return getattr(cls, "invalid_ids_error")
        return getattr(cls.getModule(), "InvalidIds")

    @classmethod
    async def ensureOne(
        cls,
        key: KeyType,
        fetcher: Callable[[KeyType], Awaitable[ActualAPIObjectImpl]],
        exception_factory: Optional[ValueExceptionFactory] = None,
    ) -> ActualAPIObjectImpl:
        try:
            return await ObjectCache.get().ensureOne(
                cls.getCacheCategory(), key, fetcher
            )
        except InvalidCacheKey as error:
            if exception_factory is None:
                exception_factory = cls.getInvalidIdError()
            raise exception_factory(value=error.key) from None

    @classmethod
    async def ensure(
        cls,
        keys: Sequence[KeyType],
        fetcher: Callable[
            [Sequence[KeyType]], Awaitable[Collection[ActualAPIObjectImpl]]
        ],
        exception_factory: Optional[ValuesExceptionFactory] = None,
    ) -> Sequence[ActualAPIObjectImpl]:
        try:
            return await ObjectCache.get().ensure(cls.getCacheCategory(), keys, fetcher)
        except InvalidCacheKeys as error:
            if exception_factory is None:
                exception_factory = cls.getInvalidIdsError()
            raise exception_factory(values=error.keys) from None

    @classmethod
    def storeOne(
        cls: Type[ActualAPIObjectImpl], obj: ActualAPIObjectImpl
    ) -> ActualAPIObjectImpl:
        return ObjectCache.get().storeOne(cls.getCacheCategory(), obj)[0]

    @classmethod
    def store(
        cls: Type[ActualAPIObjectImpl], objects: Sequence[ActualAPIObjectImpl]
    ) -> Sequence[ActualAPIObjectImpl]:
        return ObjectCache.get().store(cls.getCacheCategory(), objects)[0]


ActualAPIObjectImplWithId = TypeVar(
    "ActualAPIObjectImplWithId", bound="APIObjectImplWithId"
)


class APIObjectImplWithId(APIObjectImpl, api.APIObjectWithId):
    def __init_subclass__(cls, *, module: types.ModuleType):
        super().__init_subclass__()
        cls.setModule(module)

    def __init__(self, critic: api.critic.Critic, args: object) -> None:
        super().__init__(critic)
        self.__id = self.update(args)

    @abstractmethod
    def update(self, args: Any) -> int:
        ...

    @property
    def id(self) -> int:
        return self.__id

    def cacheKey(self) -> int:
        return self.id

    async def checkAccess(self) -> None:
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
    def getQueryByIds(
        cls,
    ) -> Optional[Callable[[api.critic.Critic, Sequence[int]], QueryResult[Any]]]:
        return None

    @classmethod
    async def doRefreshAll(
        cls,
        critic: api.critic.Critic,
        cached_objects: Collection[object],
        /,
    ) -> None:
        query_by_id = cls.getQueryByIds()
        assert query_by_id, cls
        cached_apiobjects = cast(Collection[APIObjectImplWithId], cached_objects)
        await cls.updateAll(
            cached_apiobjects,
            query_by_id(
                critic, [cached_object.id for cached_object in cached_apiobjects]
            ),
        )

    async def refresh(self: ActualAPIObjectImplWithId) -> ActualAPIObjectImplWithId:
        await self.refreshAll(self.critic, None, {self})
        return self

    @classmethod
    async def updateAll(
        cls,
        objects: Collection[APIObjectImplWithId],
        query: QueryResult[Any],
    ) -> None:
        async with query as results:
            rows = {row[0]: row async for row in results}
        for obj in objects:
            if obj.id in rows:
                obj.update(rows[obj.id])

    def getCacheKeys(self) -> Collection[object]:
        return (self.id,)

    @staticmethod
    def ids(objects: Collection[APIObjectImplWithId]) -> Sequence[int]:
        return [obj.id for obj in objects]

    @classmethod
    def getCustomCache(cls) -> Dict[object, object]:
        return ObjectCache.get().getCustom(cls)
