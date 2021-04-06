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

"""The `APIObject` class.

This class is a helper base class for all significant non-exception API classes.
Classes that are considered "insignificant" are typically simpler data
structures returned by attributes or methods on the "significant" API classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import importlib
import types
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    SupportsInt,
    TypeVar,
)

from critic import api
from critic import dbaccess


Actual = TypeVar("Actual", bound="APIObject")


class APIObject(ABC):
    """Base class of all significant API classes.

    Exposes the Critic session object as the read-only `APIObject.critic`
    attribute."""

    @property
    @abstractmethod
    def critic(self) -> api.critic.Critic:
        """The Critic session object used to fetch this object.

        The value is a `critic.api.critic.Critic` object."""
        ...

    @abstractmethod
    async def refresh(self: Actual) -> Actual:
        """Refresh the data from the database."""
        ...

    @classmethod
    def getModule(cls) -> types.ModuleType:
        """Return the module object that implements this API object type.

        This can be used to access other predictably named items from the
        module, such as the `Error` class and the `fetch()` function, in a
        generic fashion."""
        return importlib.import_module(cls.__module__)

    @classmethod
    def getResourceName(cls) -> str:
        return getattr(cls.getModule(), "resource_name")

    @classmethod
    def getTableName(cls) -> str:
        return getattr(cls.getModule(), "table_name")


class APIObjectWithId(APIObject):
    @property
    @abstractmethod
    def id(self) -> int:
        ...

    def __int__(self) -> int:
        return self.id

    def __hash__(self) -> int:
        return hash((type(self), int(self)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, APIObjectWithId):
            return False
        return isinstance(self, type(other)) and int(self) == int(other)

    def __lt__(self, other: SupportsInt) -> bool:
        return int(self) < int(other)

    def __repr__(self) -> str:
        return "%s(id=%r)" % (type(self).__name__, self.id)

    def __adapt__(self) -> dbaccess.SQLValue:
        """Adapt to SQL query parameter"""
        return int(self)

    @classmethod
    def getIdColumn(cls) -> str:
        return getattr(cls.getModule(), "id_column", "id")


T = TypeVar("T", bound=Callable[..., Any])


class FunctionRef(Generic[T]):
    __value: Optional[T]

    def __init__(self) -> None:
        self.__value = None

    def get(self) -> T:
        assert self.__value is not None
        return self.__value

    def __call__(self, value: T) -> T:
        assert self.__value is None
        self.__value = value
        return value
