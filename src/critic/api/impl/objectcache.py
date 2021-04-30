from __future__ import annotations
from collections import defaultdict

from contextvars import ContextVar
import contextvars
from typing import (
    Awaitable,
    Callable,
    ClassVar,
    Collection,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    cast,
)

from critic import api, dbaccess


class CacheableObject(Protocol):
    def getCacheKeys(self) -> Collection[object]:
        ...


CacheKeyFromArgs = Callable[[Tuple[object, ...]], object]

ObjectType = TypeVar("ObjectType", bound=CacheableObject)

KeyType = TypeVar("KeyType")


class InvalidCacheKey(Exception):
    def __init__(self, key: object):
        self.key = key


class InvalidCacheKeys(Exception):
    def __init__(self, keys: Collection[object]):
        self.keys = keys


OBJECT_CACHE: ContextVar[ObjectCache] = ContextVar("ObjectCache")


Refresher = Callable[
    [api.critic.Critic, FrozenSet[str], Collection[object]], Awaitable[None]
]


class ObjectCache:
    __refreshers: ClassVar[Dict[str, Refresher]] = {}
    __values: Dict[str, Dict[object, object]]
    __custom: Dict[object, Dict[object, object]]
    __token: contextvars.Token[ObjectCache]

    @staticmethod
    def get() -> ObjectCache:
        return OBJECT_CACHE.get()

    @staticmethod
    def create() -> ObjectCache:
        # assert OBJECT_CACHE.get(None) is None
        cache = ObjectCache()
        cache.__token = OBJECT_CACHE.set(cache)
        return cache

    @classmethod
    def registerRefresher(cls, category: str, refresher: Refresher) -> None:
        cls.__refreshers[category] = refresher

    def __init__(self) -> None:
        self.__values = defaultdict(dict)
        self.__custom = defaultdict(dict)

    def destroy(self) -> None:
        self.__values.clear()
        assert OBJECT_CACHE.get(None) is self
        OBJECT_CACHE.reset(self.__token)

    # def find(self, object_type: Type[ObjectType], object_id: object, /) -> ObjectType:
    #     return cast(ObjectType, self.__values[object_type][object_id])

    def findAll(
        self, category: str, object_type: Type[ObjectType]
    ) -> Mapping[object, ObjectType]:
        return cast(Mapping[object, ObjectType], self.__values[category])

    # def assign(self, object_type: Type[ObjectType], new_object: ObjectType, /) -> None:
    #     by_type = self.__values.setdefault(object_type, {})
    #     key = new_object.getCacheKeys()
    #     assert key not in by_type
    #     by_type[key] = new_object

    async def ensureOne(
        self,
        category: str,
        key: KeyType,
        fetcher: Callable[[KeyType], Awaitable[ObjectType]],
    ) -> ObjectType:
        cached = cast(Dict[object, ObjectType], self.__values[category])
        if key in cached:
            return cached[key]
        try:
            new_object = await fetcher(key)
        except dbaccess.ZeroRowsInResult:
            raise InvalidCacheKey(key)
        for new_key in new_object.getCacheKeys():
            assert new_key not in cached
            cached[new_key] = new_object
        try:
            return cached[key]
        except KeyError:
            raise InvalidCacheKey(key)

    async def ensure(
        self,
        category: str,
        keys: Sequence[KeyType],
        fetcher: Callable[[Sequence[KeyType]], Awaitable[Collection[ObjectType]]],
    ) -> Sequence[ObjectType]:
        cached = cast(Dict[object, ObjectType], self.__values[category])
        misses = [key for key in keys if key not in cached]
        if misses:
            for new_object in await fetcher(misses):
                for key in new_object.getCacheKeys():
                    assert key not in cached
                    cached[key] = new_object
        try:
            return [cached[key] for key in keys]
        except KeyError:
            raise InvalidCacheKeys({key for key in keys if key not in cached})

    def storeOne(self, category: str, obj: ObjectType) -> Tuple[ObjectType, bool]:
        all_objects, new_objects = self.store(category, [obj])
        return all_objects[0], bool(new_objects)

    def store(
        self, category: str, objects: Sequence[ObjectType]
    ) -> Tuple[Sequence[ObjectType], Sequence[ObjectType]]:
        cached = cast(Dict[object, ObjectType], self.__values[category])

        new_objects: List[ObjectType] = []

        def storeOne(obj: ObjectType) -> ObjectType:
            (key, *other_keys) = obj.getCacheKeys()
            if key in cached:
                assert all(cached[other_key] == cached[key] for other_key in other_keys)
                return cached[key]
            else:
                assert all(other_key not in cached for other_key in other_keys)
                cached[key] = obj
                for other_key in other_keys:
                    cached[other_key] = obj
                new_objects.append(obj)
                return obj

        return [storeOne(obj) for obj in objects], new_objects

    def getCustom(self, category: object) -> Dict[object, object]:
        return self.__custom[category]

    async def refreshAll(
        self, critic: api.critic.Critic, tables: FrozenSet[str]
    ) -> None:
        for category, cached_objects in self.__values.items():
            await ObjectCache.__refreshers[category](
                critic, tables, set(cached_objects.values())
            )
