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
import asyncio
import logging
import types
from typing import (
    Optional,
    SupportsInt,
    Callable,
    Any,
    Iterator,
    Tuple,
    Iterable,
    Dict,
    TypeVar,
    Generic,
    Sequence,
    Generator,
    Type,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import pubsub

from . import protocol

ResultType = TypeVar("ResultType")


class Result(Generic[ResultType], metaclass=abc.ABCMeta):
    __future: Optional[asyncio.Future]

    def __init__(self, transaction: api.transaction.Transaction) -> None:
        self.transaction = transaction
        self.critic = transaction.critic
        self.__future = None

    @property
    @abc.abstractmethod
    def has_result(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def result(self) -> Any:
        ...

    @property
    def future(self) -> "asyncio.Future[ResultType]":
        async def set_result() -> None:
            assert self.__future is not None
            self.__future.set_result(await self.result)

        if self.__future is None:
            loop = self.critic.loop
            self.__future = loop.create_future()
            if self.has_result:
                asyncio.ensure_future(set_result(), loop=loop)
            else:
                self.transaction.post_commit_callbacks.append(set_result)
        return self.__future

    def __await__(self) -> Generator[Any, None, ResultType]:
        return self.future.__await__()


class LazyValue(dbaccess.Adaptable):
    value: Optional[dbaccess.SQLValue] = None

    def __adapt__(self) -> dbaccess.SQLValue:
        assert self.value is not None, repr(self)
        return self.value

    def __str__(self) -> str:
        return str(self.value)

    def __call__(self, value: dbaccess.SQLValue) -> None:
        assert self.value is None
        assert value is not None
        self.value = value

    def __repr__(self) -> str:
        if self.value is None:
            return f"{type(self).__name__}(<unresolved>)"
        return f"{type(self).__name__}(value={self.value!r})"


class LazyInt(LazyValue):
    def __init__(self, source: SupportsInt = None) -> None:
        self.source = source

    def __int__(self) -> int:
        if self.source:
            return int(self.source)
        assert isinstance(self.value, int)
        return self.value

    def __call__(self, value: dbaccess.SQLValue) -> None:
        assert self.source is None
        super().__call__(value)


class LazyObject(LazyInt):
    def __init__(self) -> None:
        super().__init__()
        self.id = LazyInt(self)


ObjectType = TypeVar("ObjectType", bound=api.APIObject)


class LazyAPIObject(LazyObject, Result[ObjectType]):
    Scopes = Tuple[str, ...]

    api_module: Optional[types.ModuleType] = None
    resource_name: Optional[str] = None
    table_name: Optional[str] = None
    id_column: str = "id"

    def __init_subclass__(cls, api_module: types.ModuleType = None):
        if api_module:
            cls.api_module = api_module
            cls.resource_name = getattr(api_module, "resource_name")
            cls.table_name = getattr(api_module, "table_name")
            cls.id_column = getattr(api_module, "id_column", cls.id_column)

    def __init__(
        self,
        transaction: api.transaction.Transaction,
        *,
        callback: Callable[[Any], Any] = None,
    ) -> None:
        LazyObject.__init__(self)
        Result.__init__(self, transaction)
        transaction.publish(publisher=self)
        if callback is not None:
            self.set_callback(callback)
        assert self.resource_name
        self.channels = [pubsub.ChannelName(self.resource_name)]
        self.__payload = None

    @property
    def has_result(self) -> bool:
        return self.value is not None

    @property
    async def result(self) -> ObjectType:
        return await self.fetch(self.critic, int(self))

    def set_callback(self, callback: Callable[[api.APIObject], Any]) -> None:
        def wrapper(future: asyncio.Future) -> None:
            result = callback(future.result())
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

        self.future.add_done_callback(wrapper)

    async def fetch(self, critic: api.critic.Critic, item_id: Any) -> ObjectType:
        assert self.api_module is not None
        return await getattr(self.api_module, "fetch")(critic, item_id)

    def scopes(self) -> Scopes:
        return ()

    async def publish(
        self,
    ) -> Optional[Tuple[Sequence[pubsub.ChannelName], protocol.PublishedMessage]]:
        assert self.resource_name
        self.channels.extend(
            pubsub.ChannelName(f"{scope}/{self.resource_name}")
            for scope in self.scopes()
        )
        if self.value is None:
            logger.debug("%r: not publishing: object not created", self)
            return None
        assert isinstance(self.value, int)
        payload = await self.create_payload(self.resource_name, await self.result)
        if payload:
            logger.debug("publishing created object: %r to %r", payload, self.channels)
            return self.channels, payload
        return None

    async def create_payload(
        self, resource_name: str, subject: ObjectType, /
    ) -> protocol.CreatedAPIObject:
        return protocol.CreatedAPIObject(resource_name, subject.id)

    T = TypeVar("T", bound="LazyAPIObject[ObjectType]")

    def insert(self: T, **kwargs: dbaccess.Parameter) -> T:
        from .item import Insert

        assert self.table_name
        self.transaction.items.append(
            Insert(self.table_name, returning="id", collector=self).values(**kwargs)
        )
        return self


class GenericLazyAPIObject(LazyAPIObject[ObjectType]):
    resource_name: str

    def __init__(
        self,
        transaction: api.transaction.Transaction,
        api_module: types.ModuleType,
        *,
        callback: Callable[[api.APIObject], Any] = None,
    ) -> None:
        self.resource_name = getattr(api_module, "resource_name")
        self.table_name = getattr(api_module, "table_name")
        LazyAPIObject.__init__(self, transaction, callback=callback)
        self.api_module = api_module


class CollectCreatedObject(asyncio.Future):
    def __init__(self, expected_type: type):
        super().__init__()
        self.__expected_type = expected_type

    def __call__(self, value: api.APIObject) -> None:
        assert isinstance(value, self.__expected_type), value
        self.set_result(value)


__all__ = [
    "Result",
    "LazyValue",
    "LazyInt",
    "LazyObject",
    "LazyAPIObject",
    "GenericLazyAPIObject",
    "CollectCreatedObject",
]
