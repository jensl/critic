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

import copy
import contextlib
import itertools
import re

import api
import auth
import request
import textutils

class Error(Exception):
    pass

class PathError(Error):
    """Raised for valid paths that don't match a resource

       Results in a 404 "Not Found" response.

       Note: A "valid" path is one that could have returned a resource, had the
             system's dynamic state (database + repositories) been different."""

    http_status = 404
    title = "No such resource"

class UsageError(Error):
    """Raised for invalid paths and/or query parameters

       Results in a 400 "Bad Request" response.

       Note: An "invalid" path is one that could never (in this version of
             Critic) return any other response, regardless of the system's
             dynamic state (database + repositories.)"""

    http_status = 400
    title = "Invalid API request"

class InputError(Error):
    http_status = 400
    title = "Invalid API input"

class PermissionDenied(Error):
    http_status = 403
    title = "Permission denied"

class InternalRedirect(Exception):
    def __init__(self, resource_path, subresource_path=None,
                 value=None, values=None):
        self.resource_path = resource_path
        self.subresource_path = subresource_path or []
        self.value = value
        self.values = values

class ResourceSkipped(Exception):
    """Raised by a resource class's json() to skip the resource

       The message should explain why it was skipped, which may be
       sent to the client in a "404 Not Found" response."""
    pass

SPECIAL_QUERY_PARAMETERS = frozenset(["fields", "include", "debug"])

def _process_fields(value):
    fields = set()
    for field in value.split(","):
        fields.add(field)
        # For fields on the form 'a.b.c', add the prefixes 'a' and 'a.b' as
        # well, so that one can request inclusion of fields in sub-objects
        # without having to explicitly request the sub-object be included.
        while True:
            field, _, _ = field.rpartition(".")
            if not field:
                break
            fields.add(field)
    return fields

class Parameters(object):
    def __init__(self, critic, req):
        self.critic = critic
        self.req = req
        self.debug = req.getParameter(
            "debug", set(), filter=lambda value: set(value.split(",")))
        self.fields = req.getParameter(
            "fields", set(), filter=_process_fields)
        self.fields_per_type = {}
        self.__query_parameters = {
            name: value
            for name, value in req.getParameters().items()
            if name not in SPECIAL_QUERY_PARAMETERS }
        self.__resource_name = None
        self.range_accessed = False
        self.context = {}
        self.subresource_path = []

    def __prepareType(self, resource_type):
        if resource_type not in self.fields_per_type:
            self.fields_per_type[resource_type] = self.req.getParameter(
                "fields[%s]" % resource_type, self.fields,
                filter=_process_fields)
        return self.fields_per_type[resource_type]

    def hasField(self, resource_type, key):
        fields = self.__prepareType(resource_type)
        return not fields or key in fields

    def filtered(self, resource_type, resource_json):
        fields = self.__prepareType(resource_type)
        if fields:
            def filter_json(prefix, key, json):
                if isinstance(json, dict):
                    if key:
                        prefix += key + "."
                    return { key: filter_json(prefix, key, value)
                             for key, value in json.items()
                             if prefix + key in fields }
                else:
                    return json
            return filter_json("", "", resource_json)
        return resource_json

    @contextlib.contextmanager
    def forResource(self, resource):
        assert self.__resource_name is None
        self.__resource_name = resource.name
        yield
        self.__resource_name = None

    def getQueryParameter(self, name, converter=None, exceptions=()):
        if self.__resource_name:
            value = self.__query_parameters.get(
                "%s[%s]" % (name, self.__resource_name))
        else:
            value = None
        if value is None:
            value = self.__query_parameters.get(name)
        if value is not None and converter:
            try:
                value = converter(value)
            except exceptions:
                raise UsageError("Invalid %s parameter: %r" % (name, value))
        return value

    def getRange(self):
        self.range_accessed = True
        offset = self.getQueryParameter(
            "offset", converter=int, exceptions=ValueError)
        if offset is not None:
            if offset < 0:
                raise UsageError("Invalid offset parameter: %r" % offset)
        count = self.getQueryParameter(
            "count", converter=int, exceptions=ValueError)
        if count is not None:
            if count < 1:
                raise UsageError("Invalid count parameter: %r" % count)
        if offset and count:
            return offset, offset + count
        return offset, count

    def setContext(self, key, value):
        if key in self.context:
            existing = self.context[key]
            if existing is None or existing != value:
                self.context[key] = None
        else:
            self.context[key] = value

class Linked(object):
    def __init__(self, req):
        if req is not None:
            include = req.getParameter(
                "include", [], filter=lambda value: value.split(","))
            self.linked_per_type = { resource_type: set()
                                     for resource_type in include }

    def __getitem__(self, resource_type):
        return self.linked_per_type[resource_type]
    def __setitem__(self, resource_type, value):
        self.linked_per_type[resource_type] = value

    def isEmpty(self):
        return not any(self.linked_per_type.values())

    def add(self, resource_path, *values):
        resource_class = lookup(resource_path)
        assert all(isinstance(value, resource_class.value_class)
                   for value in values)
        linked = self.linked_per_type.get(resource_class.name)
        if linked is not None:
            linked.update(values)

    def filter_referenced(self, json):
        if isinstance(json, dict):
            return {
                key: self.filter_referenced(value)
                for key, value in json.items()
            }
        elif isinstance(json, list):
            return [self.filter_referenced(value) for value in json]
        elif type(json) in VALUE_CLASSES:
            resource_path = VALUE_CLASSES[type(json)]
            self.add(resource_path, json)
            return json.id
        else:
            return json

    def copy(self):
        return copy.deepcopy(self)

HANDLERS = {}
VALUE_CLASSES = {}

def registerHandler(path, resource_class):
    HANDLERS[path] = resource_class
    if not path.startswith("..."):
        if isinstance(resource_class.value_class, tuple):
            for value_class in resource_class.value_class:
                VALUE_CLASSES[value_class] = path
        else:
            VALUE_CLASSES[resource_class.value_class] = path

def PrimaryResource(resource_class):
    assert hasattr(resource_class, "name")
    assert hasattr(resource_class, "value_class")
    for name in ("single", "multiple", "create", "update", "delete"):
        if not hasattr(resource_class, name):
            setattr(resource_class, name, None)
    for name in ("exceptions", "objects", "lists", "maps"):
        if not hasattr(resource_class, name):
            setattr(resource_class, name, ())
    for name in ("anonymous_create", "anonymous_update", "anonymous_delete"):
        if not hasattr(resource_class, name):
            setattr(resource_class, name, False)
    contexts = getattr(resource_class, "contexts", (None,))
    if None in contexts:
        registerHandler("v1/" + resource_class.name, resource_class)
    for context in filter(None, contexts):
        registerHandler(".../%s/%s" % (context, resource_class.name),
                        resource_class)
    return resource_class

def lookup(resource_path):
    if not isinstance(resource_path, list):
        resource_path = resource_path.split("/")
    for offset in range(len(resource_path) - 1):
        if offset:
            resource_id = "/".join(["..."] + resource_path[offset:])
        else:
            resource_id = "/".join(resource_path)
        try:
            return HANDLERS[resource_id]
        except KeyError:
            continue
    else:
        raise PathError("Invalid resource: %r" % "/".join(resource_path))

def find(resource_name):
    suffix = "/" + resource_name
    return (resource_class
            for resource_id, resource_class in HANDLERS.items()
            if resource_id.endswith(suffix))

def id_or_name(argument):
    try:
        return int(argument), None
    except ValueError:
        return None, argument

def numeric_id(argument):
    try:
        value = int(argument)
        if value < 1:
            raise ValueError
        return value
    except ValueError:
        raise UsageError("Invalid numeric id: %r" % argument)

def deduce(resource_path, parameters):
    resource_class = lookup(resource_path)
    try:
        return resource_class.deduce(parameters)
    except resource_class.exceptions as error:
        raise PathError("Resource not found: %s" % error.message)

def sorted_by_id(items):
    return sorted(items, key=lambda item: item.id)

import check

from check import convert, ensure

import v1
import documentation

def getAPIVersion(req):
    path = req.path.split("/")

    assert len(path) >= 1 and path[0] == "api"

    if len(path) < 2:
        return None

    api_version = path[1]

    if api_version != "v1":
        raise PathError("Unsupported API version: %r" % api_version)

    return api_version

def finishGET(critic, req, parameters, resource_class, value, values):
    assert (value is None) != (values is None)

    api_version = getAPIVersion(req)

    try:
        if values is not None:
            values_json = []

            for value in values:
                try:
                    values_json.append(resource_class.json(value, parameters))
                except ResourceSkipped:
                    pass

            resource_json = {
                resource_class.name: values_json
            }
        else:
            try:
                resource_json = resource_class.json(value, parameters)
            except ResourceSkipped as error:
                raise PathError("Resource not found: %s" % error.message)
    except resource_class.exceptions as error:
        raise PathError("Resource not found: %s" % error.message)
    except IndexError:
        raise PathError("List index out of range")

    if req.method != "DELETE" and parameters.subresource_path:
        subresource_json = resource_json
        for component in parameters.subresource_path:
            subresource_json = subresource_json[component]
        resource_json = {
            "/".join(parameters.subresource_path): subresource_json
        }

    linked = Linked(req)

    resource_json = linked.filter_referenced(resource_json)

    if linked.linked_per_type:
        all_linked = linked.copy()

        linked_json = resource_json["linked"] = {
            resource_type: []
            for resource_type in linked.linked_per_type
        }

        while not linked.isEmpty():
            additional_linked = Linked(req)

            for resource_type, linked_values in linked.linked_per_type.items():
                resource_class = lookup([api_version, resource_type])

                for linked_value in linked_values:
                    try:
                        linked_value_json = resource_class.json(linked_value,
                                                                parameters)
                    except ResourceSkipped:
                        continue
                    linked_json[resource_type].append(
                        additional_linked.filter_referenced(linked_value_json))

            for resource_type in linked.linked_per_type.keys():
                additional_linked[resource_type] -= all_linked[resource_type]
                all_linked[resource_type] |= linked[resource_type]

            linked = additional_linked

            for linked_items in linked_json.values():
                if linked_items and "id" in linked_items[0]:
                    linked_items.sort(key=lambda item: item["id"])

    if critic.database.profiling and "dbqueries" in parameters.debug:
        import profiling
        # Sort items by accumulated time.
        items = sorted(critic.database.profiling.items(),
                       key=lambda item: item[1][1],
                       reverse=True)
        resource_json.setdefault("debug", {})["dbqueries"] = {
            "formatted": profiling.formatDBProfiling(critic.database),
            "items": [
                {
                    "query": re.sub(r"\s+", " ", query),
                    "count": count,
                    "accumulated": {
                        "time": accumulated_ms,
                        "rows": accumulated_rows
                    },
                    "maximum": {
                        "time": maximum_ms,
                        "rows": maximum_rows
                    }
                }
                for query, (count,
                            accumulated_ms, maximum_ms,
                            accumulated_rows, maximum_rows) in items
            ]
        }

    return resource_json

def requireSignIn(critic):
    if critic.actual_user is None:
        raise UsageError("Sign-in required")

def finishPOST(critic, req, parameters, resource_class, value, values, data):
    if not resource_class.anonymous_create:
        requireSignIn(critic)

    if (value or values) and not parameters.subresource_path:
        raise UsageError("Invalid POST request")

    if not resource_class.create:
        raise UsageError("Resource class does not support creating: "
                         % resource_class.name)

    while True:
        try:
            value, values = resource_class.create(
                parameters, value, values, data)
        except resource_class.exceptions as error:
            raise UsageError(error.message)
        except InternalRedirect as redirect:
            resource_class = lookup(redirect.resource_path)
            parameters.subresource_path = redirect.subresource_path
            value = redirect.value
            values = redirect.values
        else:
            break

    return finishGET(critic, req, parameters, resource_class, value, values)

def finishPUT(critic, req, parameters, resource_class, value, values, data):
    if not resource_class.anonymous_update:
        requireSignIn(critic)

    if not (value or values):
        raise UsageError("Invalid PUT request")

    if not resource_class.update:
        raise UsageError("Resource class does not support updating: "
                         % resource_class.name)

    try:
        resource_class.update(parameters, value, values, data)
    except resource_class.exceptions as error:
        raise UsageError(error.message)

    return finishGET(critic, req, parameters, resource_class, value, values)

def finishDELETE(critic, req, parameters, resource_class, value, values):
    if not resource_class.anonymous_delete:
        requireSignIn(critic)

    if not (value or values):
        raise UsageError("Invalid DELETE request")

    if not resource_class.delete:
        raise UsageError("Resource class does not support deleting: "
                         % resource_class.name)

    try:
        return_value = resource_class.delete(parameters, value, values)
    except resource_class.exceptions as error:
        raise UsageError(error.message)

    if return_value is None:
        raise request.NoContent()

    value, values = return_value

    return finishGET(critic, req, parameters, resource_class, value, values)

def handleRequestInternal(critic, req):
    api_version = getAPIVersion(req)

    if not api_version:
        if req.method == "GET":
            documentation.describeRoot()
        else:
            raise UsageError("Invalid %s request" % req.method)

    prefix = [api_version]
    parameters = Parameters(critic, req)

    path = req.path.rstrip("/").split("/")[2:]

    if not path:
        if req.method == "GET":
            describe_parameter = parameters.getQueryParameter("describe")
            if describe_parameter:
                v1.documentation.describeResource(describe_parameter)
            v1.documentation.describeVersion()
        else:
            raise UsageError("Invalid %s request" % req.method)

    if req.method in ("POST", "PUT"):
        try:
            data = textutils.json_decode(req.read())
        except ValueError:
            raise UsageError("Invalid %s request body" % req.method)

    context = None
    resource_class = None

    while True:
        next_component = path.pop(0)

        if resource_class and (next_component in resource_class.objects or
                               next_component in resource_class.lists or
                               next_component in resource_class.maps):
            subresource_id = []
            subresource_path = []

            while True:
                subresource_id.append(next_component)
                subresource_path.append(next_component)

                if "/".join(subresource_id) in resource_class.objects:
                    pass
                elif "/".join(subresource_id) in resource_class.lists:
                    if path:
                        try:
                            subresource_path.append(int(path[0]))
                        except ValueError:
                            raise UsageError(
                                "Item identifier must be an integer: %r"
                                % path[0])
                        else:
                            del path[0]
                elif "/".join(subresource_id) in resource_class.maps:
                    if path:
                        subresource_path.append(path[0])
                else:
                    raise PathError("Invalid resource: %r / %r"
                                    % ("/".join(resource_path),
                                       "/".join(subresource_id)))

                if not path:
                    break

                next_component = path.pop(0)

            parameters.subresource_path = subresource_path
            break

        resource_path = prefix + [next_component]
        resource_class = lookup(resource_path)

        prefix.append(resource_class.name)

        value = None
        values = None

        resource_id = "/".join(resource_path)

        try:
            if path and resource_class.single:
                arguments = filter(None, path.pop(0).split(","))
                if len(arguments) == 0 or (len(arguments) > 1 and path):
                    raise UsageError("Invalid resource path: %s" % req.path)
                if len(arguments) == 1:
                    with parameters.forResource(resource_class):
                        value = resource_class.single(parameters, arguments[0])
                    assert isinstance(value, resource_class.value_class)
                    if not path:
                        break
                else:
                    with parameters.forResource(resource_class):
                        values = [resource_class.single(parameters, argument)
                                  for argument in arguments]
                    assert all(isinstance(value, resource_class.value_class)
                               for value in values)
                    break
            elif not path:
                if req.method == "POST":
                    break
                if not resource_class.multiple:
                    raise UsageError("Resource requires an argument: %s"
                                     % resource_id)
                with parameters.forResource(resource_class):
                    values = resource_class.multiple(parameters)
                if isinstance(values, resource_class.value_class):
                    value, values = values, None
                elif not parameters.range_accessed:
                    begin, end = parameters.getRange()
                    values = itertools.islice(values, begin, end)
                break
        except resource_class.exceptions as error:
            raise PathError("Resource not found: %s" % error.message)

    if values and not isinstance(values, list):
        values = list(values)

    if req.method == "GET":
        return finishGET(critic, req, parameters, resource_class, value, values)
    elif req.method == "POST":
        return finishPOST(
            critic, req, parameters, resource_class, value, values, data)
    elif req.method == "PUT":
        return finishPUT(
            critic, req, parameters, resource_class, value, values, data)
    elif req.method == "DELETE":
        return finishDELETE(
            critic, req, parameters, resource_class, value, values)

def handleRequest(critic, req):
    try:
        return handleRequestInternal(critic, req)
    except (api.PermissionDenied, auth.AccessDenied) as error:
        raise PermissionDenied(error.message)
