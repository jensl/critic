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
import contextvars
import inspect
import logging
from typing import (
    AsyncContextManager,
    AsyncIterator,
    ClassVar,
    Collection,
    ContextManager,
    Optional,
    Any,
    List,
    Dict,
    Set,
    Callable,
    Coroutine,
    Tuple,
    FrozenSet,
    Iterator,
    TypeVar,
    Awaitable,
    Sequence,
    Iterable,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import critic as public
from critic import dbaccess
from .objectcache import ObjectCache


SESSION: contextvars.ContextVar[public.Critic] = contextvars.ContextVar("session")


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
    __value: ClassVar[Optional[Settings]] = None

    def __init__(self, settings: Iterable[api.systemsetting.SystemSetting]) -> None:
        super().__init__()
        for setting in settings:
            self._add(setting)

    @staticmethod
    def is_loaded() -> bool:
        return Settings.__value is not None

    @staticmethod
    def get() -> Settings:
        if Settings.__value is None:
            raise public.SessionNotInitialized()
        return Settings.__value

    @staticmethod
    async def load(critic: public.Critic) -> Settings:
        try:
            settings = await api.systemsetting.fetchAll(critic)
        except dbaccess.ProgrammingError:
            settings = []
        Settings.__value = Settings(settings)
        return Settings.get()


@public.settingsImpl
def settings() -> Settings:
    return Settings.get()


T = TypeVar("T")


class Critic(public.Critic):
    __session_profiles: List[api.accesscontrolprofile.AccessControlProfile]
    __actual_user: Optional[api.user.User]
    __access_token: Optional[api.accesstoken.AccessToken]
    __authentication_labels: Optional[FrozenSet[str]]
    __access_control_profiles: Set[api.accesscontrolprofile.AccessControlProfile]
    __external_account: Optional[api.externalaccount.ExternalAccount]
    __close_tasks: List[public.CloseTask]
    __effective_user: Optional[api.user.User]
    __slice: Optional[Tuple[int, Optional[int]]]

    def __init__(
        self, connection: dbaccess.Connection, session_type: public.SessionType
    ) -> None:
        self.__task = asyncio.current_task()
        self.__is_closing = self.__is_closed = False
        self.__session_type = session_type
        self.__session_profiles = []
        self.__database = connection
        self.__tracer = DefaultTracer()
        self.__actual_user = None
        self.__access_token = None
        self.__authentication_labels = None
        self.__access_control_profiles = set()
        self.__external_account = None
        self.__close_tasks = []
        self.__effective_user = None
        self.__slice = None

    @property
    def is_closed(self) -> bool:
        return self.__is_closed

    @property
    def is_closing(self) -> bool:
        return self.__is_closing

    @property
    def session_type(self) -> public.SessionType:
        return self.__session_type

    async def _ensureBaseProfile(self) -> None:
        if not self.__session_profiles:
            self.__session_profiles.insert(
                0, await api.accesscontrolprofile.fetch(self)
            )

    @property
    async def session_profiles(
        self,
    ) -> FrozenSet[api.accesscontrolprofile.AccessControlProfile]:
        await self._ensureBaseProfile()
        return frozenset(self.__session_profiles)

    @property
    def effective_user(self) -> api.user.User:
        if self.__effective_user:
            return self.__effective_user
        if self.__actual_user:
            return self.__actual_user
        if self.__session_type == "system":
            return api.user.system(self)
        return api.user.anonymous(self)

    @contextlib.contextmanager
    def __setEffectiveUser(self, user: api.user.User) -> Iterator[None]:
        api.PermissionDenied.raiseIfRegularUser(user.critic)
        previous = self.__effective_user
        self.__effective_user = user
        try:
            yield
        finally:
            self.__effective_user = previous

    def asUser(self, user: api.user.User) -> ContextManager[None]:
        return self.__setEffectiveUser(user)

    @property
    def actual_user(self) -> Optional[api.user.User]:
        return self.__actual_user

    @property
    def authentication_labels(self) -> Optional[FrozenSet[str]]:
        return self.__authentication_labels

    @property
    def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        return self.__access_token

    @property
    def external_account(self) -> Optional[api.externalaccount.ExternalAccount]:
        return self.__external_account

    def hasRole(self, role: str) -> Optional[bool]:
        return self.__actual_user.hasRole(role) if self.__actual_user else None

    @property
    def database(self) -> dbaccess.Connection:
        assert asyncio.current_task() == self.__task
        return self.__database

    @contextlib.contextmanager
    def user_session(self) -> Iterator[None]:
        assert self.__session_type == "system"
        actual_user = self.__actual_user
        self.__session_type = "user"
        self.__actual_user = None
        try:
            yield
        finally:
            self.__session_type = "system"
            self.__actual_user = actual_user
            self.__access_token = None
            self.__authentication_labels = None

    async def setActualUser(self, user: api.user.User) -> None:
        assert not user.is_anonymous
        assert self.__session_type != "user" or self.__actual_user is None, (
            self.__session_type,
            self.__actual_user,
        )
        self.__session_type = "user"
        self.__actual_user = user
        if user.status == "retired":
            async with api.transaction.start(user.critic) as transaction:
                await transaction.modifyUser(user).setStatus("current")

    async def setAccessToken(self, access_token: api.accesstoken.AccessToken) -> None:
        assert self.__access_token is None
        assert self.__actual_user == await access_token.user
        self.__access_token = access_token
        profile = await access_token.profile
        if profile is not None:
            await self._ensureBaseProfile()
            self.__session_profiles.append(profile)

    def setAuthenticationLabels(self, labels: Collection[str]) -> None:
        assert self.__authentication_labels is None
        self.__authentication_labels = frozenset(labels)

    def addAccessControlProfile(
        self, profile: api.accesscontrolprofile.AccessControlProfile
    ) -> None:
        self.__access_control_profiles.add(profile)

    async def setExternalAccount(
        self, external_account: api.externalaccount.ExternalAccount
    ) -> None:
        assert (
            self.__actual_user is None
            or self.__actual_user == await external_account.user
        )
        assert self.__external_account is None
        assert self.__session_type == "user"
        self.__external_account = external_account

    async def __loadSettings(self) -> Settings:
        return await Settings.load(self)

    async def wakeup_service(self, service_name: str) -> None:
        from critic import background

        await background.utils.wakeup(service_name)

    def enableTracing(self) -> None:
        raise Exception("NOT IMPLEMENTED")

    def addCloseTask(self, fn: public.CloseTask) -> None:
        self.__close_tasks.append(fn)

    async def close(self) -> None:
        if self.__is_closed:
            return
        self.__is_closing = True
        if self.__close_tasks:
            tasks = [asyncio.create_task(fn()) for fn in self.__close_tasks]
            done, _ = await asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception:
                    logger.exception("Close task failed!")
        try:
            # for Implementation, cached_objects in self.__objects_cache.items():
            #     if hasattr(Implementation, "close"):
            #         getattr(Implementation, "close")(cached_objects)
            if self.__database:
                await self.__database.close()
        finally:
            self.__is_closed = True

    async def transactionEnded(self, tables: Collection[str]) -> None:
        await ObjectCache.get().refreshAll(self, frozenset(tables))

    @contextlib.contextmanager
    def __pushSlice(self, offset: int, count: Optional[int]) -> Iterator[None]:
        assert self.__slice is None, "slice already set"
        self.__slice = (offset, count)
        yield
        assert self.__slice is None, "set limit never consumed"

    def pushSlice(
        self, *, offset: int = 0, count: Optional[int] = None
    ) -> ContextManager[None]:
        return self.__pushSlice(offset, count)

    def popSlice(self) -> Tuple[int, Optional[int]]:
        if self.__slice is None:
            raise public.NoSlice()
        try:
            return self.__slice
        finally:
            self.__slice = None

    @staticmethod
    def fromWrapper(critic: public.Critic) -> Critic:
        return critic._impl  # type: ignore

    @staticmethod
    @contextlib.asynccontextmanager
    async def startSession(
        session_type: public.SessionType,
    ) -> AsyncIterator[public.Critic]:
        async with dbaccess.connection() as connection:
            critic = Critic(connection, session_type)
            cache = ObjectCache.create()
            await critic.__loadSettings()
            if critic.session_type in ("system", "testing"):
                critic.__actual_user = api.user.system(critic)
            token = SESSION.set(critic)
            try:
                yield critic
            finally:
                cache.destroy()
                SESSION.reset(token)
                await critic.close()


@public.startSessionImpl
def startSession(
    for_user: bool,
    for_system: bool,
    for_testing: bool,
) -> AsyncContextManager[public.Critic]:
    session_type: public.SessionType

    if for_user:
        session_type = "user"
    elif for_system:
        session_type = "system"
    else:
        session_type = "testing"

    return Critic.startSession(session_type)


@public.getSessionImpl
def getSession() -> public.Critic:
    return SESSION.get()
