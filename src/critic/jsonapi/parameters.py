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
import functools
import itertools
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from types import ModuleType
from typing import (
    Any,
    Awaitable,
    Callable,
    Collection,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    Mapping,
    Iterator,
    Protocol,
    cast,
    overload,
)

from critic import api

from . import getAPIVersion
from .exceptions import UsageError
from .types import Request


T = TypeVar("T")


def _process_fields(value: str) -> Tuple[Set[str], Set[str]]:
    included = set()
    excluded = set()
    included_names, _, excluded_names = value.partition("-")
    if included_names:
        for name in included_names.split(","):
            included.add(name)
            # For included fields on the form 'a.b.c', add the prefixes 'a.' and
            # 'a.b.' as well, which causes the sub-objects containing 'a.b.c' to
            # be included at all.
            while True:
                name, period, _ = name.rpartition(".")
                if not period:
                    break
                included.add(name + period)
    if excluded_names:
        # Note: no need to handle prefixes as above here, obviously.
        excluded.update(excluded_names.split(","))
    return included, excluded


IncludeOptions = Dict[str, Union[bool, int, str]]


def _process_include(value: str) -> Mapping[str, IncludeOptions]:
    included = {}
    for item in value.split(","):
        resource_name, _, options_string = item.partition(":")
        options: IncludeOptions = {}
        if options_string:
            for option_string in options_string.split(":"):
                name, eq, value = option_string.partition("=")
                if not eq:
                    options[name] = True
                elif name == "limit":
                    try:
                        options[name] = int(value)
                    except TypeError:
                        raise UsageError("Invalid include limit: %r" % value)
                else:
                    options[name] = value
        included[resource_name] = options
    return included


SPECIAL_QUERY_PARAMETERS = frozenset(["fields", "include", "debug"])


class Parameters(object):
    fields_per_type: Dict[str, Set[str]]
    context: Dict[str, Any]
    __resource_name: Optional[str]
    __linked: Dict[str, Set[Any]]
    primary_resource_type: Optional[str]
    api_object_cache: Dict[int, Any]

    def __init__(self, critic: api.critic.Critic, req: Request):
        self.critic = critic
        self.req = req
        self.api_version = getAPIVersion(req)
        self.debug = req.getParameter(
            "debug", set(), filter=lambda value: set(value.split(","))
        )
        self.fields = req.getParameter("fields", (set(), set()), filter=_process_fields)
        self.include = req.getParameter("include", {}, filter=_process_include)
        self.fields_per_type = {}
        self.__query_parameters = {
            name: value
            for name, value in req.getParameters().items()
            if name not in SPECIAL_QUERY_PARAMETERS
        }
        self.__resource_name = None
        self.range_accessed = False
        self.context = {}
        self.output_format = self.__query_parameters.get("output_format", "default")
        self.__linked = defaultdict(set)
        self.primary_resource_type = None
        self.api_object_cache = {}

    def __prepareType(self, resource_type: str) -> Set[str]:
        if resource_type not in self.fields_per_type:
            if resource_type == self.primary_resource_type:
                default_fields = self.fields
            else:
                default_fields = set(), set()
            self.fields_per_type[resource_type] = self.req.getParameter(
                "fields[%s]" % resource_type, default_fields, filter=_process_fields
            )
        return self.fields_per_type[resource_type]

    def hasField(self, resource_type: str, key: str) -> bool:
        included, excluded = self.__prepareType(resource_type)
        if included:
            return key in included
        if excluded:
            return key not in excluded
        return True

    def getFieldsForType(self, resource_type: str) -> Set[str]:
        return self.__prepareType(resource_type)

    @contextlib.contextmanager
    def forResource(self, resource: Type[ResourceClass]) -> Iterator[None]:
        assert self.__resource_name is None
        self.__resource_name = resource.name
        yield
        self.__resource_name = None

    @overload
    def getQueryParameter(
        self, name: str, /, *, choices: Collection[str] = None,
    ) -> Optional[str]:
        ...

    @overload
    def getQueryParameter(
        self, name: str, default: str, /, *, choices: Collection[str] = None
    ) -> str:
        ...

    @overload
    def getQueryParameter(
        self,
        name: str,
        /,
        *,
        converter: Callable[[str], T],
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> Optional[T]:
        ...

    @overload
    def getQueryParameter(
        self,
        name: str,
        default: str,
        /,
        *,
        converter: Callable[[str], T],
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> T:
        ...

    def getQueryParameter(
        self,
        name: str,
        default: str = None,
        /,
        *,
        choices: Collection[str] = None,
        converter: Callable[[str], T] = None,
        exceptions: Tuple[Type[BaseException], ...] = (ValueError,),
    ) -> Optional[Union[str, T]]:
        value: Optional[str] = None
        if self.__resource_name:
            value = self.__query_parameters.get("%s[%s]" % (name, self.__resource_name))
        if value is None:
            value = self.__query_parameters.get(name)
        if value is None:
            value = default
        if value is None:
            return None
        if converter:
            try:
                return converter(value)
            except exceptions as error:
                raise UsageError.invalidParameter(name, value, message=str(error))
        if choices:
            if value not in choices:
                choices = sorted(choices)
                expected = ", ".join(choices[:-1]) + " and " + choices[-1]
                raise UsageError.invalidParameter(
                    name, value, expected=f"one of {expected}"
                )
        return value

    def getRange(self) -> Tuple[Optional[int], Optional[int]]:
        self.range_accessed = True
        offset = self.getQueryParameter("offset", converter=int)
        if offset is not None:
            if offset < 0:
                raise UsageError("Invalid offset parameter: %r" % offset)
        count = self.getQueryParameter("count", converter=int)
        if count is not None:
            if count < 1:
                raise UsageError("Invalid count parameter: %r" % count)
        if offset and count:
            return offset, offset + count
        return offset, count

    @contextlib.contextmanager
    def setSlice(self) -> Iterator[None]:
        begin, end = self.getRange()
        if begin is None or end is None:
            yield
        else:
            offset = begin
            if begin is None:
                count = end
            elif end is not None:
                count = end - begin
            with self.critic.pushSlice(offset=offset, count=count):
                yield

    def setContext(self, key: str, value: api.APIObject) -> None:
        if key in self.context:
            existing = self.context[key]
            if existing is None or existing != value:
                self.context[key] = None
        else:
            self.context[key] = value

    def getLinked(self, resource_type: str) -> Set[Any]:
        return self.__linked.pop(resource_type, set())

    def addLinked(self, value: Any) -> None:
        self.__linked[ResourceClass.find(value).name].add(value)


from .resourceclass import ResourceClass
