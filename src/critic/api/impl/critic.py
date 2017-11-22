# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
import inspect
import logging
import threading
from collections import defaultdict
from typing import (
    AsyncContextManager,
    AsyncIterator,
    Optional,
    Union,
    Mapping,
    Any,
    List,
    Dict,
    Set,
    Callable,
    Coroutine,
    DefaultDict,
    Tuple,
    FrozenSet,
    Iterator,
    Type,
    TypeVar,
    Awaitable,
    Sequence,
    Iterable,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import dbaccess


class NoKey(object):
    pass


class DefaultTracer:
    enabled = False

    @contextlib.contextmanager
    def __call__(self, label: str, **kwargs: Any) -> Any:
        yield


class SettingsGroup:
    __items: Dict[str, Any]

    def __init__(self, prefix: str = "") -> None:
        self.__items = {}
        self.__prefix = prefix
        self.keys = self.__items.keys
        self.values = self.__items.values
        self.items = self.__items.items

    def __repr__(self) -> str:
        return "%s :: %r" % (self.__prefix, self.__items)

    # def keys(self):
    #     return self.__items.keys()

    # def values(self):
    #     return self.__items.values()

    # def items(self):
    #     return self.__items.items()

    def __getattr__(self, key: str) -> Any:
        try:
            return self.__items[key]
        except KeyError:
            raise AttributeError(key)

    def __contains__(self, key: str) -> bool:
        return key in self.__items

    def _add(self, setting: api.systemsetting.SystemSetting) -> None:
        prefix, _, rest = setting.key[len(self.__prefix) :].partition(".")
        existing = self.__items.get(prefix)
        if rest:
            if existing is None:
                existing = self.__items[prefix] = SettingsGroup(
                    self.__prefix + prefix + "."
                )
            else:
                assert isinstance(existing, SettingsGroup)
            existing._add(setting)
        else:
            assert existing is None
            self.__items[prefix] = setting.value

    def __bool__(self) -> bool:
        return bool(self.__items)


class Settings(SettingsGroup):
    def __init__(self, settings: Iterable[api.systemsetting.SystemSetting]) -> None:
        super().__init__()
        for setting in settings:
            self._add(setting)


settings = None
settings_lock = threading.Lock()

T = TypeVar("T")

CloseTask = Callable[[], Coroutine[Any, Any, None]]


class Critic(object):
    session_profiles: List[api.accesscontrolprofile.AccessControlProfile]
    database: Optional[dbaccess.Connection]
    actual_user: Optional[api.user.User]
    access_token: Optional[api.accesstoken.AccessToken]
    authentication_labels: Optional[FrozenSet[str]]
    access_control_profiles: Set[api.accesscontrolprofile.AccessControlProfile]
    external_account: Optional[api.externalaccount.ExternalAccount]
    close_tasks: List[CloseTask]
    __objects_cache: Dict[type, Dict[Any, api.APIObject]]
    __custom_cache: Dict[type, Dict[Any, Any]]
    __effective_user: Optional[api.user.User]
    __slice: Optional[Tuple[int, Optional[int]]]
    __critical_sections: DefaultDict[str, asyncio.Lock]

    def __init__(
        self, session_type: api.critic.SessionType, loop: asyncio.AbstractEventLoop
    ) -> None:
        self.is_closing = self.is_closed = False
        self.session_type = session_type
        self.session_profiles = []
        self.database = None
        self.tracer = DefaultTracer()
        self.actual_user = None
        self.access_token = None
        self.authentication_labels = None
        self.access_control_profiles = set()
        self.external_account = None
        self.loop = loop
        self.close_tasks = []
        self.__objects_cache = {}
        self.__custom_cache = {}
        self.__effective_user = None
        self.__slice = None
        self.__critical_sections = defaultdict(asyncio.Lock)

    def setDatabase(self, database: dbaccess.Connection) -> None:
        self.database = database

    def getEffectiveUser(self, critic: api.critic.Critic) -> api.user.User:
        if self.__effective_user:
            return self.__effective_user
        if self.actual_user:
            return self.actual_user
        if self.session_type == "system":
            return api.user.system(critic)
        return api.user.anonymous(critic)

    async def _ensureBaseProfile(self, wrapper: api.critic.Critic) -> None:
        if not self.session_profiles:
            self.session_profiles.insert(
                0, await api.accesscontrolprofile.fetch(wrapper)
            )

    async def getSessionProfiles(
        self, wrapper: api.critic.Critic
    ) -> FrozenSet[api.accesscontrolprofile.AccessControlProfile]:
        await self._ensureBaseProfile(wrapper)
        return frozenset(self.session_profiles)

    @contextlib.contextmanager
    def setEffectiveUser(self, user: api.user.User) -> Iterator:
        api.PermissionDenied.raiseIfRegularUser(user.critic)
        previous = self.__effective_user
        self.__effective_user = user
        try:
            yield
        finally:
            self.__effective_user = previous

    def hasRole(self, role: str) -> Optional[bool]:
        return self.actual_user.hasRole(role) if self.actual_user else None

    @contextlib.contextmanager
    def user_session(self) -> Iterator[None]:
        assert self.session_type == "system"
        actual_user = self.actual_user
        self.session_type = "user"
        self.actual_user = None
        try:
            yield
        finally:
            self.session_type = "system"
            self.actual_user = actual_user
            self.access_token = None
            self.authentication_labels = None

    async def setActualUser(self, user: api.user.User) -> None:
        self.session_type = "user"
        self.actual_user = user
        if user.status == "retired":
            async with api.transaction.start(user.critic) as transaction:
                transaction.modifyUser(user).setStatus("current")

    async def setAccessToken(self, access_token: api.accesstoken.AccessToken) -> None:
        assert self.actual_user == await access_token.user
        self.access_token = access_token
        profile = await access_token.profile
        if profile is not None:
            await self._ensureBaseProfile(access_token.critic)
            self.session_profiles.append(profile)

    async def loadSettings(self, critic: api.critic.Critic) -> Settings:
        global settings, settings_lock
        if not settings:
            with settings_lock:
                if not settings:
                    settings = Settings(await api.systemsetting.fetchAll(critic))
        return settings

    def lookupObject(self, cls: type, key: Any) -> api.APIObject:
        return self.__objects_cache[cls][key]

    def lookupObjects(self, cls: type) -> Mapping[Any, api.APIObject]:
        return self.__objects_cache[cls]

    def initializeObjects(self, cls: type) -> Dict[Any, api.APIObject]:
        return self.__objects_cache.setdefault(cls, {})

    def assignObjects(self, cls: type, key: Any, value: api.APIObject) -> None:
        assert isinstance(value, getattr(cls, "wrapper_class"))
        self.initializeObjects(cls)[key] = value

    def lookupCustom(self, cls: type, key: Any, default: Any = None) -> Any:
        cache = self.__custom_cache.get(cls, None)
        return cache.get(key, default) if cache else default

    def assignCustom(self, cls: type, key: Any, value: Any) -> None:
        self.__custom_cache.setdefault(cls, {})[key] = value

    def criticalSection(self, key: str) -> asyncio.Lock:
        return self.__critical_sections[key]

    def getEventLoop(self) -> asyncio.AbstractEventLoop:
        return self.loop

    def ensure_future(self, coroutine: Coroutine[Any, Any, T]) -> "asyncio.Future[T]":
        return asyncio.ensure_future(coroutine, loop=self.getEventLoop())

    def check_future(
        self, coroutine: Coroutine[Any, Any, T], callback: Callable[[T], None] = None
    ) -> asyncio.Future:
        def check(future: "asyncio.Future[T]") -> None:
            try:
                result = future.result()
            except Exception:
                logger.exception("Checked coroutine failed!")
            else:
                if callback is not None:
                    callback(result)

        future = self.ensure_future(coroutine)
        future.add_done_callback(check)
        return future

    async def gather(
        self, coroutines_or_futures: Tuple[Awaitable, ...], return_exceptions: bool
    ) -> Sequence[Any]:
        """Call asyncio.gather() with the correct `loop` argument"""
        return await asyncio.gather(
            *coroutines_or_futures,
            loop=self.getEventLoop(),
            return_exceptions=return_exceptions,
        )

    async def maybe_await(self, coroutine_or_future: Any) -> Any:
        if inspect.isawaitable(coroutine_or_future):
            return await coroutine_or_future
        return coroutine_or_future

    async def wakeup_service(self, service_name: str) -> None:
        from critic import background

        await background.utils.wakeup(service_name)

    def enableTracing(self) -> None:
        raise Exception("NOT IMPLEMENTED")

    def addCloseTask(self, fn: CloseTask) -> None:
        assert self.loop is not None
        self.close_tasks.append(fn)

    async def close(self) -> None:
        if self.is_closed:
            return
        self.is_closing = True
        if self.close_tasks:
            tasks = [self.ensure_future(fn()) for fn in self.close_tasks]
            done, _ = await asyncio.wait(tasks, loop=self.loop)
            for future in done:
                try:
                    future.result()
                except Exception:
                    logger.exception("Close task failed!")
        try:
            for Implementation, cached_objects in self.__objects_cache.items():
                if hasattr(Implementation, "close"):
                    getattr(Implementation, "close")(cached_objects)
            if self.database:
                await self.database.close()
        finally:
            self.database = None
            self.is_closed = True

    @staticmethod
    async def transactionEnded(critic: api.critic.Critic, tables: Set[str]) -> None:
        objects_cache = critic._impl.__objects_cache
        for Implementation, cached_objects in objects_cache.items():
            if hasattr(Implementation, "refresh"):
                await getattr(Implementation, "refresh")(critic, tables, cached_objects)

    @contextlib.contextmanager
    def pushSlice(self, offset: int, count: Optional[int]) -> Iterator:
        assert self.__slice is None, "slice already set"
        self.__slice = (offset, count)
        yield
        assert self.__slice is None, "set limit never consumed"

    def popSlice(self) -> Tuple[int, Optional[int]]:
        if self.__slice is None:
            raise api.critic.NoSlice()
        try:
            return self.__slice
        finally:
            self.__slice = None


@contextlib.asynccontextmanager
async def _startSession(critic: api.critic.Critic) -> AsyncIterator[api.critic.Critic]:
    async with dbaccess.connection() as connection:
        critic._impl.setDatabase(connection)
        await critic._impl.loadSettings(critic)
        if critic.session_type in ("system", "testing"):
            critic._impl.actual_user = api.user.system(critic)
        try:
            yield critic
        finally:
            await critic._impl.close()


def startSession(
    for_user: bool,
    for_system: bool,
    for_testing: bool,
    loop: Optional[asyncio.AbstractEventLoop],
) -> AsyncContextManager[api.critic.Critic]:
    session_type: api.critic.SessionType

    if for_user:
        session_type = "user"
    elif for_system:
        session_type = "system"
    else:
        session_type = "testing"

    if loop is None:
        loop = asyncio.get_event_loop()

    return _startSession(api.critic.Critic(Critic(session_type, loop)))
