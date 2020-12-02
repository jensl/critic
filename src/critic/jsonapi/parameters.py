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

import contextlib
from dataclasses import dataclass
from typing import (
    Any,
    Collection,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Iterator,
    Protocol,
)

from critic import api
from .query import Query
from .types import Request

T = TypeVar("T")
APIObject = TypeVar("APIObject", bound=api.APIObject)

Fields = Tuple[Collection[str], Collection[str]]


@dataclass
class Cookie:
    value: str
    secure: bool


class Cookies:
    def __init__(self) -> None:
        self.set_cookies: Dict[str, Cookie] = {}
        self.del_cookies: List[str] = []

    def set_cookie(self, name: str, value: str, *, secure: bool) -> None:
        self.set_cookies[name] = Cookie(value, secure)

    def del_cookie(self, name: str) -> None:
        self.del_cookies.append(name)


class Parameters(Protocol):
    @property
    def request(self) -> Request:
        ...

    @property
    def critic(self) -> api.critic.Critic:
        ...

    @property
    def query(self) -> Query:
        ...

    @property
    def cookies(self) -> Cookies:
        ...

    @property
    def include(self) -> Mapping[str, Mapping[str, object]]:
        ...

    @property
    def context(self) -> Dict[str, Any]:
        ...

    @property
    def primary_resource_type(self) -> str:
        ...

    @primary_resource_type.setter
    def primary_resource_type(self, value: str) -> None:
        ...

    @property
    def range_accessed(self) -> bool:
        ...

    @property
    def output_format(self) -> Literal["static", "default"]:
        ...

    @property
    def debug(self) -> Collection[str]:
        ...

    @property
    def api_version(self) -> Literal["v1"]:
        ...

    @property
    def api_object_cache(self) -> Dict[int, object]:
        ...

    def hasField(self, resource_type: str, key: str) -> bool:
        ...

    def getFieldsForType(self, resource_type: str) -> Fields:
        ...

    @contextlib.contextmanager
    def forResource(self, resource_type: str) -> Iterator[None]:
        ...

    def getRange(self) -> Tuple[Optional[int], Optional[int]]:
        ...

    @contextlib.contextmanager
    def setSlice(self) -> Iterator[None]:
        ...

    def setContext(self, key: str, value: api.APIObject) -> None:
        ...

    def getLinked(self, resource_type: str) -> Set[Any]:
        ...

    def addLinked(self, value: Any) -> None:
        ...

    def in_context(
        self, value_class: Type[APIObject], default_value: Optional[APIObject] = None
    ) -> Optional[APIObject]:
        ...

    async def deduce(self, value_class: Type[APIObject]) -> Optional[APIObject]:
        ...

    async def fromParameter(
        self, value_class: Type[APIObject], name: str
    ) -> Optional[APIObject]:
        ...
