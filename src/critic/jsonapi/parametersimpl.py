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
from collections import defaultdict
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    Mapping,
    Iterator,
    cast,
)

from critic import api

from .exceptions import UsageError
from .parameters import APIObject, Fields, Parameters, Cookies
from .query import Query
from .resourceclass import ResourceClass, HANDLERS, VALUE_CLASSES
from .utils import getAPIVersion
from .types import Request


T = TypeVar("T")


def _process_fields(value: str) -> Fields:
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
    if not value.strip():
        return {}
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


def get_parameter(
    request: Request,
    name: str,
    default: T,
    filter_value: Callable[[str], T],
) -> T:
    if name in request.query:
        return filter_value(request.query[name])
    return default


class ParametersImpl(Parameters):
    __debug: Collection[str]
    __fields: Fields
    __fields_per_type: Dict[str, Fields]
    __context: Dict[str, Any]
    __resource_type: Optional[str]
    __linked: Dict[str, Set[Any]]
    __primary_resource_type: Optional[str]
    __api_object_cache: Dict[int, Any]

    def __init__(self, critic: api.critic.Critic, request: Request):
        self.__critic = critic
        self.__request = request
        self.__cookies = Cookies()
        self.__api_version = getAPIVersion(request)
        self.__debug = get_parameter(
            request, "debug", set(), lambda value: set(value.split(","))
        )
        default_fields: Fields = (set(), set())
        self.__fields = get_parameter(
            request, "fields", default_fields, _process_fields
        )
        default_include: Mapping[str, IncludeOptions] = {}
        self.__include = get_parameter(
            request, "include", default_include, _process_include
        )
        self.__fields_per_type = {}
        self.__query_parameters: Mapping[str, str] = {
            name: value
            for name, value in request.query.items()
            if name not in SPECIAL_QUERY_PARAMETERS
        }
        self.__query = Query(self.__query_parameters, self.__get_resource_type)
        self.__resource_type = None
        self.__range_accessed = False
        self.__context = {}
        self.__output_format = self.__query.get(
            "output_format", "default", choices=("default", "static")
        )
        self.__linked = defaultdict(set)
        self.__primary_resource_type = None
        self.__api_object_cache = {}

    def __get_resource_type(self) -> Optional[str]:
        return self.__resource_type

    def __prepareType(self, resource_type: str) -> Fields:
        if resource_type not in self.__fields_per_type:
            default_fields: Fields
            if resource_type == self.primary_resource_type:
                default_fields = self.__fields
            else:
                default_fields = set(), set()
            self.__fields_per_type[resource_type] = get_parameter(
                self.__request,
                "fields[%s]" % resource_type,
                default_fields,
                _process_fields,
            )
        return self.__fields_per_type[resource_type]

    @property
    def request(self) -> Request:
        return self.__request

    @property
    def critic(self) -> api.critic.Critic:
        return self.__critic

    @property
    def query(self) -> Query:
        return self.__query

    @property
    def cookies(self) -> Cookies:
        return self.__cookies

    @property
    def include(self) -> Mapping[str, Mapping[str, object]]:
        return self.__include

    @property
    def context(self) -> Dict[str, Any]:
        return self.__context

    @property
    def primary_resource_type(self) -> str:
        assert self.__primary_resource_type
        return self.__primary_resource_type

    @primary_resource_type.setter
    def primary_resource_type(self, value: str) -> None:
        self.__primary_resource_type = value

    @property
    def range_accessed(self) -> bool:
        return self.__range_accessed

    @property
    def output_format(self) -> Literal["static", "default"]:
        return cast(Literal["static", "default"], self.__output_format)

    @property
    def debug(self) -> Collection[str]:
        return self.__debug

    @property
    def api_version(self) -> Literal["v1"]:
        return self.__api_version

    @property
    def api_object_cache(self) -> Dict[int, object]:
        return self.__api_object_cache

    def hasField(self, resource_type: str, key: str) -> bool:
        included, excluded = self.__prepareType(resource_type)
        if included:
            return key in included
        if excluded:
            return key not in excluded
        return True

    def getFieldsForType(self, resource_type: str) -> Fields:
        return self.__prepareType(resource_type)

    @contextlib.contextmanager
    def forResource(self, resource_type: str) -> Iterator[None]:
        assert self.__resource_type is None
        self.__resource_type = resource_type
        yield
        self.__resource_type = None

    def getRange(self) -> Tuple[Optional[int], Optional[int]]:
        self.__range_accessed = True
        offset = self.query.get("offset", converter=int)
        if offset is not None:
            assert isinstance(offset, int)
            if offset < 0:
                raise UsageError("Invalid offset parameter: %r" % offset)
        count = self.query.get("count", converter=int)
        if count is not None:
            assert isinstance(count, int)
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
            else:
                count = None
            with self.critic.pushSlice(offset=offset, count=count):
                yield

    def setContext(self, key: str, value: api.APIObject) -> None:
        if key in self.__context:
            existing = self.__context[key]
            if existing is None or existing != value:
                self.__context[key] = None
        else:
            self.__context[key] = value

    def getLinked(self, resource_type: str) -> Set[Any]:
        return self.__linked.pop(resource_type, set())

    def addLinked(self, value: Any) -> None:
        self.__linked[ResourceClass.find(value).name].add(value)

    def in_context(
        self, value_class: Type[APIObject], default_value: Optional[APIObject] = None
    ) -> Optional[APIObject]:
        resource_class = cast(
            Type[ResourceClass[APIObject]], HANDLERS[VALUE_CLASSES[value_class]]
        )
        return self.__context.get(resource_class.name, default_value)

    async def deduce(self, value_class: Type[APIObject]) -> Optional[APIObject]:
        resource_class = cast(
            Type[ResourceClass[APIObject]], HANDLERS[VALUE_CLASSES[value_class]]
        )
        return await resource_class.deduce(self)

    async def fromParameter(
        self, value_class: Type[APIObject], name: str
    ) -> Optional[APIObject]:
        resource_class = cast(
            Type[ResourceClass[APIObject]], HANDLERS[VALUE_CLASSES[value_class]]
        )
        return await resource_class.fromParameter(self, name)
