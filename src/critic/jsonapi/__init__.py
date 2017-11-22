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
    Literal,
    cast,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import auth
from ..wsgi import request
from critic.base import asyncutils
from critic.base.profiling import timed

from .exceptions import (
    Error,
    PathError,
    UsageError,
    InputError,
    PermissionDenied,
    ResultDelayed,
    ResourceSkipped,
)


def getAPIVersion(req: Request) -> Literal["v1"]:
    path = req.path.split("/")

    assert len(path) >= 1 and path[0] == "api"

    if len(path) < 2:
        raise PathError("Missing API version")

    api_version = path[1]

    if api_version != "v1":
        raise PathError("Unsupported API version: %r" % api_version)

    return api_version


from .types import Request


T = TypeVar("T")
U = TypeVar("U")


def identity(value: str) -> str:
    return value


from .parameters import Parameters
from .linked import Linked
from .valuewrapper import ValueWrapper, plain, immediate, basic_list


# def find(resource_name: str) -> Any:
#     suffix = "/" + resource_name
#     return (
#         resource_class
#         for resource_id, resource_class in HANDLERS.items()
#         if resource_id.endswith(suffix)
#     )


from .utils import (
    id_or_name,
    numeric_id,
    maybe_await,
    sorted_by_id,
    many,
    delay,
)

from . import check

from .check import convert, ensure
from .values import Values, SingleValue, MultipleValues

from .types import JSONInput, JSONResult


from .resourceclass import NotSupported, ResourceClass, VALUE_CLASSES

from . import v1
from . import documentation


from .reduce import reduceValue, reduceValues
from .filterjson import filter_json


async def finishLinked(
    api_version: Literal["v1"], linked: Linked, included_values: Set[Any]
) -> JSONResult:
    if not linked.linked_per_type:
        return None

    parameters = linked.parameters
    all_linked = Linked(parameters)
    linked_json: Dict[str, Union[Literal["limited"], List[JSONResult]]] = {
        resource_type: [] for resource_type in linked.linked_per_type
    }

    while not linked.isEmpty():
        additional_linked = Linked(parameters)

        for resource_type, linked_values in linked.linked_per_type.items():
            options = parameters.include[resource_type]
            if not linked_values:
                continue
            if linked_json[resource_type] == "limited":
                continue
            already_linked = all_linked[resource_type]
            if already_linked:
                linked_values -= already_linked
                if not linked_values:
                    continue
            if "limit" in options:
                if len(already_linked) + len(linked_values) > options["limit"]:
                    linked_json[resource_type] = "limited"
                    continue
            linked_resource_class = ResourceClass.lookup([api_version, resource_type])
            if linked_resource_class.name == parameters.primary_resource_type:
                # This is the primary resource class, so filter out values
                # that were part of the primary result.
                linked_values -= included_values
                if not linked_values:
                    continue
            resource_linked_json = linked_json[resource_type]
            if resource_linked_json == "limited":
                continue
            resource_linked_json.extend(
                await filter_json(
                    parameters,
                    additional_linked,
                    linked_resource_class,
                    await reduceValues(
                        parameters,
                        linked_resource_class.json,
                        MultipleValues(linked_values),
                        set(),
                    ),
                )
            )
            all_linked[resource_type] |= linked_values

        linked = additional_linked

        for resource_type, linked_items in linked_json.items():
            if linked_items == "limited":
                continue

            linked_items.sort(
                key=ResourceClass.lookup([api_version, resource_type]).sort_key
            )

    return linked_json


async def finishGET(
    critic: api.critic.Critic,
    req: Request,
    parameters: Parameters,
    resource_class: Type[ResourceClass],
    values: Values[T],
) -> JSONResult:
    included_values: Set[T] = set()
    resource_json: Any

    try:
        if isinstance(values, MultipleValues):
            resource_json = await reduceValues(
                parameters, resource_class.json, values, included_values
            )
        else:
            assert isinstance(values, SingleValue)
            try:
                resource_json = await reduceValue(
                    parameters, resource_class.json, values.get()
                )
            except ResourceSkipped as error:
                raise PathError(str(error))
            try:
                included_values.add(values.get())
            except TypeError:
                pass
    except resource_class.exceptions as error:
        raise PathError(str(error))
    # except IndexError:
    #     raise PathError("List index out of range")

    parameters.primary_resource_type = resource_class.name

    linked = Linked(parameters)

    if not isinstance(resource_json, list) and parameters.output_format == "static":
        resource_json = [resource_json]

    if isinstance(resource_json, list):
        top_json = {
            resource_class.name: await filter_json(
                parameters, linked, resource_class, resource_json
            )
        }
    else:
        [top_json] = await filter_json(
            parameters, linked, resource_class, [resource_json]
        )

    if parameters.include:
        linked = await finishLinked(getAPIVersion(req), linked, included_values)
        if linked is not None:
            top_json["linked"] = linked

    if "dbqueries" in parameters.debug:
        # from ..base import profiling
        # # Sort items by accumulated time.
        # items = sorted(critic.database.profiling.items(),
        #                key=lambda item: item[1][1],
        #                reverse=True)
        top_json.setdefault("debug", {})["dbqueries"] = {
            # "formatted": profiling.formatDBProfiling(critic.database),
            "items": [
                {
                    "statement": statement,
                    "count": details.count,
                    "accumulated": {
                        "time": details.accumulated_time,
                        "rows": details.accumulated_rows,
                    },
                    "maximum": {
                        "time": details.maximum_time,
                        "rows": details.maximum_rows,
                    },
                }
                for statement, details in critic.database.executed_statements
            ]
        }

    if "tracing" in parameters.debug:

        def trace_json(trace: Any) -> Any:
            return {
                "label": trace.label,
                "begin": trace.begin,
                "end": trace.end,
                "children": [trace_json(child) for child in trace.children],
                "args": trace.args,
            }

        top_json.setdefault("debug", {})["tracing"] = trace_json(critic.tracer.traces())

    return top_json


def requireSignIn(critic: api.critic.Critic) -> None:
    if critic.actual_user is None:
        raise UsageError("Sign-in required")


async def finishPOST(
    critic: api.critic.Critic,
    req: Request,
    parameters: Parameters,
    resource_class: Type[ResourceClass],
    data: Any,
) -> JSONResult:
    if not resource_class.anonymous_create:
        requireSignIn(critic)

    # if not parameters.subresource_path:
    #     raise UsageError("Invalid POST request")

    if not resource_class.create:
        raise UsageError(
            "Resource class does not support creating: " % resource_class.name
        )

    while True:
        try:
            values = Values.make(await resource_class.create(parameters, data))
            assert all(
                isinstance(value, resource_class.value_class) for value in values
            )
        except resource_class.exceptions as error:
            raise UsageError(str(error), error=error)
        else:
            break

    return await finishGET(critic, req, parameters, resource_class, values)


async def finishPUT(
    critic: api.critic.Critic,
    req: Request,
    parameters: Parameters,
    resource_class: Type[ResourceClass],
    values: Values,
    data: Any,
) -> JSONResult:
    if not resource_class.anonymous_update:
        requireSignIn(critic)

    if isinstance(data, list):
        assert not values
        try:
            values = Values.make(await resource_class.update_many(parameters, data))
        except NotSupported:
            raise UsageError(
                "Resource class does not support updating: %s" % resource_class.name
            )
        except resource_class.exceptions as error:
            raise UsageError(str(error))
    elif values:
        try:
            await resource_class.update(parameters, values, data)
        except NotSupported:
            raise UsageError(
                "Resource class does not support updating: %s" % resource_class.name
            )
        except resource_class.exceptions as error:
            raise UsageError(str(error))

    return await finishGET(critic, req, parameters, resource_class, values)


async def finishDELETE(
    critic: api.critic.Critic,
    req: Request,
    parameters: Parameters,
    resource_class: Type[ResourceClass],
    values: Values,
) -> JSONResult:
    if not resource_class.anonymous_delete:
        requireSignIn(critic)

    resource_ids: List[int]

    if parameters.output_format == "static":
        resource_ids = [resource.id for resource in values]

    try:
        return_value = await resource_class.delete(parameters, values)
    except NotSupported:
        raise UsageError(
            "Resource class does not support deleting: %s" % resource_class.name
        )
    except resource_class.exceptions as error:
        raise UsageError(str(error))

    if return_value is None:
        if parameters.output_format == "static":
            top_json: JSONResult = {"deleted": {resource_class.name: resource_ids}}
            linked = await finishLinked(getAPIVersion(req), Linked(parameters), set())
            if linked is not None:
                top_json["linked"] = linked
            return top_json

        raise request.NoContent()

    return await finishGET(
        critic, req, parameters, resource_class, Values.make(return_value)
    )


from .evaluate import evaluateSingle, evaluateMany, evaluateMultiple


async def handleRequestInternal(critic: api.critic.Critic, req: Request) -> JSONResult:
    parameters = Parameters(critic, req)

    if "dbqueries" in parameters.debug:
        critic.database.enable_accounting()

    if not parameters.api_version:
        if req.method == "GET":
            documentation.describeRoot()
        else:
            raise UsageError("Invalid %s request" % req.method)

    prefix: List[str] = [parameters.api_version]
    path = req.path.rstrip("/").split("/")[2:]

    if not path:
        if req.method == "GET":
            describe_parameter = parameters.getQueryParameter("describe")
            if describe_parameter:
                v1.documentation.describeResource(describe_parameter)
            v1.documentation.describeVersion()
        else:
            raise UsageError("Invalid %s request" % req.method)

    data: Optional[JSONInput] = None

    if req.method in ("POST", "PUT"):
        try:
            data = json.loads(await req.read())
        except ValueError:
            raise UsageError("Invalid %s request body" % req.method)

    resource_class: Optional[Type[ResourceClass]] = None
    resource_path: List[str] = []

    while True:
        next_component = path.pop(0)

        # if resource_class and (
        #     next_component in resource_class.objects
        #     or next_component in resource_class.lists
        #     or next_component in resource_class.maps
        # ):
        #     subresource_id = []
        #     subresource_path = []

        #     while True:
        #         subresource_id.append(next_component)
        #         subresource_path.append(next_component)

        #         if "/".join(subresource_id) in resource_class.objects:
        #             pass
        #         elif "/".join(subresource_id) in resource_class.lists:
        #             if path:
        #                 try:
        #                     subresource_path.append(int(path[0]))
        #                 except ValueError:
        #                     raise UsageError(
        #                         "Item identifier must be an integer: %r" % path[0]
        #                     )
        #                 else:
        #                     del path[0]
        #         elif "/".join(subresource_id) in resource_class.maps:
        #             if path:
        #                 subresource_path.append(path[0])
        #         else:
        #             raise PathError(
        #                 "Invalid resource: %r / %r"
        #                 % ("/".join(resource_path), "/".join(subresource_id))
        #             )

        #         if not path:
        #             break

        #         next_component = path.pop(0)

        #     parameters.subresource_path = subresource_path
        #     break

        resource_path = prefix + [next_component]
        resource_class = ResourceClass.lookup(resource_path)

        prefix.append(resource_class.name)

        values = None

        resource_id = "/".join(resource_path)

        try:
            if path and resource_class.single:
                arguments: Sequence[str] = list(filter(None, path.pop(0).split(",")))
                if len(arguments) == 0 or (len(arguments) > 1 and path):
                    raise UsageError("Invalid resource path: %s" % req.path)
                if req.method == "POST" and not path:
                    raise UsageError("Invalid resource path for POST: %s" % req.path)
                try:
                    if len(arguments) == 1:
                        values = await evaluateSingle(
                            parameters, resource_class, arguments[0]
                        )
                    else:
                        values = await evaluateMany(
                            parameters, resource_class, arguments
                        )
                except resource_class.exceptions as error:
                    if parameters.output_format == "static":
                        raise PathError(str(error))
                    raise
                if len(arguments) > 1 or not path:
                    break
            elif not path:
                if req.method == "POST":
                    break
                elif req.method == "PUT" and isinstance(data, list):
                    break
                try:
                    values = await evaluateMultiple(parameters, resource_class)
                except NotSupported:
                    raise UsageError("Resource requires an argument: %s" % resource_id)
                break
        except resource_class.exceptions as error:
            raise PathError(str(error))

    if path:
        raise UsageError("Invalid path")

    if req.method == "GET":
        assert values is not None
        return await finishGET(critic, req, parameters, resource_class, values)
    elif req.method == "POST":
        return await finishPOST(critic, req, parameters, resource_class, data)
    elif req.method == "PUT":
        assert values is not None
        return await finishPUT(critic, req, parameters, resource_class, values, data)
    elif req.method == "DELETE":
        assert values is not None
        return await finishDELETE(critic, req, parameters, resource_class, values)

    raise UsageError(f"Unsupported method: {req.method}")


async def handleRequest(critic: api.critic.Critic, req: Request) -> JSONResult:
    try:
        return await handleRequestInternal(critic, req)
    except (api.PermissionDenied, auth.AccessDenied) as error:
        raise PermissionDenied(str(error))
    except api.ResultDelayedError as error:
        raise ResultDelayed("Please try again later: %s" % error)


__all__ = ["check", "convert", "ensure", "Nullable"]
