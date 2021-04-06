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

from abc import ABC, abstractmethod
import asyncio
import contextlib
import logging
import types
from typing import (
    Collection,
    Literal,
    FrozenSet,
    Optional,
    AsyncContextManager,
    Any,
    TypeVar,
    Awaitable,
    Callable,
    ContextManager,
    Tuple,
    Type,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import dbaccess
from .apiobject import FunctionRef


class SessionNotInitialized(Exception):
    pass


class NoSlice(Exception):
    """Raised by Critic.popSlice() if no slice has been set"""

    pass


SessionType = Literal["user", "system", "testing"]
CloseTask = Callable[[], Awaitable[None]]

T = TypeVar("T")


class Critic(ABC):
    SESSION_TYPES: FrozenSet[SessionType] = frozenset(["user", "system", "testing"])

    def __init__(self, impl: Any) -> None:
        self._impl = impl

    @abstractmethod
    async def close(self) -> None:
        ...

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    @property
    @abstractmethod
    def is_closed(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_closing(self) -> bool:
        ...

    @property
    @abstractmethod
    def session_type(self) -> SessionType:
        ...

    @property
    @abstractmethod
    async def session_profiles(
        self,
    ) -> FrozenSet[api.accesscontrolprofile.AccessControlProfile]:
        """The access control profiles in effect for this session

        The profiles are returned as a set of `api.accesscontrolprofile.
        AccessControlProfile` objects."""
        ...

    @property
    @abstractmethod
    def effective_user(self) -> api.user.User:
        ...

    @abstractmethod
    def asUser(self, user: api.user.User) -> ContextManager[None]:
        ...

    @property
    @abstractmethod
    def actual_user(self) -> Optional[api.user.User]:
        ...

    @property
    @abstractmethod
    def authentication_labels(self) -> Optional[FrozenSet[str]]:
        ...

    @property
    @abstractmethod
    def access_token(self) -> Optional[api.accesstoken.AccessToken]:
        """Access token used to authenticate"""
        ...

    @property
    @abstractmethod
    def external_account(self) -> Optional[api.externalaccount.ExternalAccount]:
        """External account used to authenticate user"""
        ...

    @abstractmethod
    def hasRole(self, role: str) -> Optional[bool]:
        ...

    @property
    @abstractmethod
    def database(self) -> dbaccess.Connection:
        ...

    @property
    def system_email(self) -> str:
        return getSystemEmail()

    def query(
        self, query: str, **parameters: dbaccess.Parameter
    ) -> AsyncContextManager[dbaccess.ResultSet[dbaccess.SQLRow]]:
        return self.database.query(query, **parameters)

    def transaction(self) -> dbaccess.Transaction:
        return self.database.transaction()

    @abstractmethod
    async def wakeup_service(self, service_name: str) -> None:
        ...

    @abstractmethod
    def user_session(self) -> ContextManager[None]:
        ...

    @abstractmethod
    async def setActualUser(self, user: api.user.User) -> None:
        ...

    @abstractmethod
    async def setAccessToken(self, access_token: api.accesstoken.AccessToken) -> None:
        """Set the access token used to authenticate"""
        ...

    @abstractmethod
    def setAuthenticationLabels(self, labels: Collection[str]) -> None:
        ...

    @abstractmethod
    def addAccessControlProfile(
        self, profile: api.accesscontrolprofile.AccessControlProfile
    ) -> None:
        ...

    @abstractmethod
    async def setExternalAccount(
        self, external_account: api.externalaccount.ExternalAccount
    ) -> None:
        ...

    @abstractmethod
    def enableTracing(self) -> None:
        ...

    @abstractmethod
    def addCloseTask(self, task: CloseTask) -> None:
        ...

    @abstractmethod
    async def transactionEnded(self, tables: Collection[str]) -> None:
        ...

    @abstractmethod
    def pushSlice(
        self, *, offset: int = 0, count: Optional[int] = None
    ) -> ContextManager[None]:
        ...

    @abstractmethod
    def popSlice(self) -> Tuple[int, Optional[int]]:
        ...


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
