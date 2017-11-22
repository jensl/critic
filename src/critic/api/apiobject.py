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

import importlib
import types
from typing import Any, Generic, TypeVar, SupportsInt

from critic import api
from critic import dbaccess


class APIObject:
    """Base class of all significant API classes.

    Exposes the Critic session object as the read-only `APIObject.critic`
    attribute."""

    def __init__(self, critic: api.critic.Critic, impl: Any):
        """Initialize API object.

        The APIObject class should not be instantiated directly, and nor should
        typically any of its sub-classes. Individual API modules provide
        `fetch()` functions (and others) that create the objects.

        Args:
            critic (critic.api.critic.Critic): The current session.
            impl: The implementation part."""
        self.__critic = critic
        self.__impl = impl

    def __int__(self) -> int:
        try:
            return getattr(self, "id")
        except AttributeError:
            raise TypeError("object is not hashable") from None

    def __hash__(self) -> int:
        return hash((type(self), int(self)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, APIObject):
            return False
        try:
            return type(self) == type(other) and int(self) == int(other)
        except TypeError:
            return False

    def __lt__(self, other: object) -> bool:
        assert type(self) == type(other)
        return int(self) < int(other)  # type: ignore

    def __repr__(self) -> str:
        return "%s(id=%r)" % (type(self).__name__, getattr(self, "id", "N/A"))

    def __adapt__(self) -> dbaccess.SQLValue:
        """Adapt to SQL query parameter"""
        return int(self)

    @property
    def id(self) -> Any:
        raise AttributeError(f"{type(self).__name__} has no id")

    @property
    def critic(self) -> api.critic.Critic:
        """The Critic session object used to fetch this object.

        The value is a `critic.api.critic.Critic` object."""
        return self.__critic

    @property
    def _impl(self) -> Any:
        """Underlying implementation part.

        This value should not be used outside the implementation of the API."""
        return self.__impl

    def _set_impl(self, impl: Any) -> None:
        """Set the underlying implementation part.

        This method should not be called outside the implementation of the API.
        """
        self.__impl = impl

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
