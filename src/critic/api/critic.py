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
import logging
import types
from typing import (
    Collection,
    Literal,
    FrozenSet,
    Iterator,
    Optional,
    AsyncContextManager,
    Any,
    Union,
    Coroutine,
    TypeVar,
    Awaitable,
    Callable,
    ContextManager,
    Sequence,
    Tuple,
    Type,
)

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import dbaccess


class SessionNotInitialized(Exception):
    pass


class NoSlice(Exception):
    """Raised by Critic.popSlice() if no slice has been set"""

    pass


SessionType = Literal["user", "system", "testing"]

T = TypeVar("T")


class Critic:
    SESSION_TYPES: FrozenSet[SessionType] = frozenset(["user", "system", "testing"])

    def __init__(self, impl: Any) -> None:
        self._impl = impl

    async def close(self) -> None:
        await self._impl.close()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    @property
    def is_closed(self) -> bool:
        return self._impl.is_closed

    @property
    def is_closing(self) -> bool:
        return self._impl.is_closing

    @property
    def session_type(self) -> SessionType:
        return self._impl.session_type

    @property
    async def session_profiles(
        self,
    ) -> FrozenSet[api.accesscontrolprofile.AccessControlProfile]:
        """The access control profiles in effect for this session

        The profiles are returned as a set of `api.accesscontrolprofile.
        AccessControlProfile` objects."""
        return await self._impl.getSessionProfiles(self)

    @property
    def effective_user(self) -> api.user.User:
        return self._impl.getEffectiveUser(self)

    @contextlib.contextmanager
    def asUser(self, user: api.user.User) -> Iterator[None]:
        assert isinstance(user, api.user.User)
        with self._impl.setEffectiveUser(user):
            yield

    @property
    def actual_user(self) -> Optional[api.user.User]:
        return self._impl.actual_user

    @property
    def authentication_labels(self) -> Optional[FrozenSet[str]]:
        return self._impl.authentication_labels

    @property
    def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        """Access token used to authenticate"""
        return self._impl.access_token

    @property
    def external_account(self) -> Optional[api.externalaccount.ExternalAccount]:
        """External account used to authenticate user"""
        return self._impl.external_account

    def hasRole(self, role: str) -> Optional[bool]:
        return self._impl.hasRole(role)

    @property
    def database(self) -> dbaccess.Connection:
        assert self._impl.database
        return self._impl.database

    @property
    def system_email(self) -> str:
        return getSystemEmail()

    def query(
        self, query: str, **parameters: dbaccess.Parameter
    ) -> AsyncContextManager[dbaccess.ResultSet[Any]]:
        assert self.database is not None
        return self.database.query(query, **parameters)  # type: ignore

    def transaction(self) -> dbaccess.Transaction:
        assert self.database is not None
        return self.database.transaction()

    @property
    def tracer(self) -> Any:
        return self._impl.tracer

    def ensure_future(self, coroutine: Coroutine[Any, Any, T]) -> "asyncio.Future[T]":
        return self._impl.ensure_future(coroutine)

    def check_future(
        self,
        coroutine: Coroutine[Any, Any, T],
        callback: Optional[Callable[[T], None]] = None,
    ) -> "asyncio.Future[T]":
        return self._impl.check_future(coroutine, callback)

    async def gather(
        self, *coroutines_or_futures: Awaitable[Any], return_exceptions: bool = False
    ) -> Sequence[Any]:
        return await self._impl.gather(coroutines_or_futures, return_exceptions)

    async def maybe_await(self, coroutine_or_future: Union[Awaitable[T], T]) -> T:
        return await self._impl.maybe_await(coroutine_or_future)

    async def wakeup_service(self, service_name: str) -> None:
        return await self._impl.wakeup_service(service_name)

    @contextlib.contextmanager
    def user_session(self) -> Iterator[None]:
        assert self.session_type == "system"
        with self._impl.user_session():
            yield

    async def setActualUser(self, user: api.user.User) -> None:
        assert not user.is_anonymous
        assert self.session_type != "user" or self.actual_user is None, (
            self.session_type,
            self.actual_user,
        )
        await self._impl.setActualUser(user)

    async def setAccessToken(self, access_token: api.accesstoken.AccessToken) -> None:
        """Set the access token used to authenticate"""
        assert self._impl.access_token is None
        await self._impl.setAccessToken(access_token)

    def setAuthenticationLabels(self, labels: Collection[str]) -> None:
        assert self._impl.authentication_labels is None
        self._impl.authentication_labels = frozenset(labels)

    def addAccessControlProfile(
        self, profile: api.accesscontrolprofile.AccessControlProfile
    ) -> None:
        self._impl.access_control_profiles.add(profile)

    async def setExternalAccount(
        self, external_account: api.externalaccount.ExternalAccount
    ) -> None:
        assert (
            self.actual_user is None or self.actual_user == await external_account.user
        )
        assert self.external_account is None
        assert self.session_type == "user"
        self._impl.external_account = external_account

    def enableTracing(self) -> None:
        """Enable tracing of (some) function calls"""
        self._impl.enableTracing()

    def addCloseTask(self, fn: Callable[[], Awaitable[None]]) -> None:
        self._impl.addCloseTask(fn)

    def pushSlice(
        self, *, offset: int = 0, count: Optional[int] = None
    ) -> ContextManager[None]:
        return self._impl.pushSlice(offset, count)

    def popSlice(self) -> Tuple[int, Optional[int]]:
        return self._impl.popSlice()


startSessionImpl: FunctionRef[
    Callable[[bool, bool, bool], AsyncContextManager[Critic]]
] = FunctionRef()


def startSession(
    *,
    for_user: bool = False,
    for_system: bool = False,
    for_testing: bool = False,
) -> AsyncContextManager[Critic]:
    assert sum((for_user, for_system, for_testing)) == 1
    return startSessionImpl.get()(for_user, for_system, for_testing)


getSessionImpl: FunctionRef[Callable[[], Critic]] = FunctionRef()


def getSession() -> Critic:
    return getSessionImpl.get()()


settingsImpl: FunctionRef[Callable[[], Any]] = FunctionRef()


def settings() -> Any:
    return settingsImpl.get()()


def getSystemEmail() -> str:
    system_email = settings().system.email
    if system_email is None:
        system_username = base.configuration()["system.username"]
        system_hostname = settings().system.hostname
        system_email = f"{system_username}@{system_hostname}"
    return system_email


RowType = TypeVar("RowType")


class Query(AsyncContextManager[dbaccess.ResultSet[RowType]]):
    inner: AsyncContextManager[dbaccess.ResultSet[RowType]]

    def __init__(
        self, critic: Critic, query: str, **parameters: dbaccess.Parameter
    ) -> None:
        self.inner = dbaccess.Query[RowType](
            critic.database.cursor(), query, **parameters
        )

    async def __aenter__(self) -> dbaccess.ResultSet[RowType]:
        return await self.inner.__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[types.TracebackType],
    ) -> Any:
        return await self.inner.__aexit__(exc_type, exc, tb)
