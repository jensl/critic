# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

from contextvars import ContextVar
import json
import os
import sys
from typing import (
    Mapping,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
    Union,
)


class Error(Exception):
    pass


class ImplementationError(Error):
    pass


class InvalidConfiguration(Error):
    pass


class MissingConfiguration(Error):
    pass


class UninitializedDatabase(Error):
    pass


def in_virtualenv() -> bool:
    return sys.prefix != sys.base_prefix


def home_dir() -> str:
    return os.environ.get(
        "CRITIC_HOME", sys.prefix if in_virtualenv() else "/var/lib/critic"
    )


def settings_dir() -> str:
    if "CRITIC_HOME" in os.environ:
        return os.path.join(os.environ["CRITIC_HOME"], "etc")
    # If installed in a virtual environment (default case) then return a sub-
    # directory inside the virtual environment.
    if sys.prefix != sys.base_prefix:
        return os.path.join(sys.prefix, "etc")
    # Otherwise, fall back to a reasonable system directory.
    return "/etc/critic"


DatabaseParameter = Union[int, str]
DatabaseParameters = TypedDict(
    "DatabaseParameters",
    {
        "args": Sequence[str],
        "kwargs": Mapping[str, DatabaseParameter],
    },
)

Configuration = TypedDict(
    "Configuration",
    {
        "database.parameters": DatabaseParameters,
        "paths.data": str,
        "paths.executables": str,
        "paths.home": str,
        "paths.logs": str,
        "paths.repositories": str,
        "paths.runtime": str,
        "paths.scratch": str,
        "paths.source": Optional[str],
        "services.host": str,
        "services.port": int,
        "system.flavor": str,
        "system.identity": str,
        "system.username": str,
        "system.groupname": str,
    },
)

_CONFIGURATION: ContextVar[Configuration] = ContextVar("configuration")


def configuration() -> Configuration:
    global _CONFIGURATION
    try:
        return _CONFIGURATION.get()
    except LookupError:
        pass

    configuration_json_path = os.path.join(settings_dir(), "configuration.json")
    try:
        with open(configuration_json_path) as file:
            configuration_json = file.read()
    except OSError:
        raise MissingConfiguration(configuration_json_path)

    try:
        configuration = json.loads(configuration_json)
    except ValueError:
        raise InvalidConfiguration(configuration_json)

    _CONFIGURATION.set(configuration)
    return configuration


T = TypeVar("T")


def asserted(value: Optional[T]) -> T:
    assert value is not None
    return value


from . import asyncutils

# from . import dbaccess
# from . import mimetype

__all__ = ["asyncutils"]
