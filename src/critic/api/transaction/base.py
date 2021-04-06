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

from abc import ABC, abstractmethod
from collections import deque
import logging
from typing import (
    AsyncContextManager,
    Collection,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Any,
    Dict,
    Set,
    List,
    Iterator,
    Iterable,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess

from .protocol import PublishedMessage
from .types import Publisher, AsyncCallback

T = TypeVar("T")


class Shared:
    __items: Dict[Any, Any]

    def __init__(self) -> None:
        self.__items = {}

    def __iter__(self) -> Iterator[Any]:
        return iter(self.__items.keys())

    def ensure(self, item: T) -> T:
        if item not in self.__items:
            self.__items[item] = item
        return self.__items[item]


class Finalizer:
    tables: Iterable[str] = ()

    def __init__(self, *key: object):
        self.__key = (type(self), *key)

    def __hash__(self) -> int:
        return hash(self.__key)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Finalizer) and self.__key == other.__key

    def should_run_after(self, other: Finalizer) -> bool:
        return False

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        raise Exception("Finalizer sub-class must override `__call__`")


class Finalizers:
    __tables: Set[str]
    __items: List[Finalizer]
    __items_set: Set[Finalizer]

    def __init__(self) -> None:
        self.__tables = set()
        self.__items = []
        self.__items_set = set()

    @property
    def tables(self) -> Collection[str]:
        return self.__tables

    def __iter__(self) -> Iterator[Finalizer]:
        queue = deque(self.__items)
        while queue:
            item = queue.popleft()
            if any(item.should_run_after(other) for other in queue):
                queue.append(item)
                continue
            yield item

    def add(self, finalizer: Finalizer) -> bool:
        if finalizer in self.__items_set:
            return False
        self.__tables.update(finalizer.tables)
        self.__items.append(finalizer)
        self.__items_set.add(finalizer)
        return True


ReturnType = TypeVar("ReturnType", covariant=True)


class Executable(Protocol[ReturnType]):
    @property
    def table_names(self) -> Collection[str]:
        ...

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor, /
    ) -> ReturnType:
        ...


class Savepoint(Protocol):
    async def run_finalizers(self) -> None:
        ...


class TransactionBase(ABC):
    pre_commit_callbacks: List[AsyncCallback]
    post_commit_callbacks: List[AsyncCallback]

    def __init__(self, critic: api.critic.Critic) -> None:
        self.critic = critic
        self.pre_commit_callbacks = []
        self.post_commit_callbacks = []

    @property
    @abstractmethod
    def tables(self) -> Set[str]:
        ...

    @property
    @abstractmethod
    def finalizers(self) -> Finalizers:
        ...

    @property
    @abstractmethod
    def shared(self) -> Shared:
        ...

    @abstractmethod
    async def lock(self, table: str, **columns: dbaccess.Parameter) -> None:
        ...

    @property
    @abstractmethod
    def has_savepoint(self) -> bool:
        ...

    @abstractmethod
    def savepoint(self, name: str) -> AsyncContextManager[Savepoint]:
        ...

    @abstractmethod
    def publish(
        self,
        *,
        message: Optional[PublishedMessage] = None,
        publisher: Optional[Publisher] = None,
    ) -> None:
        ...

    @abstractmethod
    def wakeup_service(self, service_name: str) -> None:
        ...

    @abstractmethod
    async def execute(self, executable: Executable[ReturnType]) -> ReturnType:
        ...
