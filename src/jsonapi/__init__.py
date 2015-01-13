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

import sys
import copy
import contextlib
import itertools

import request
import textutils

class Error(Exception):
    pass

class PathError(Error):
    http_status = 404
    title = "No such resource"

class UsageError(Error):
    http_status = 400
    title = "Invalid API request"

SPECIAL_QUERY_PARAMETERS = frozenset(["fields", "include"])

class Parameters(object):
    def __init__(self, req):
        self.req = req
        self.fields = req.getParameter(
            "fields", set(), filter=lambda value: set(value.split(",")))
        self.fields_per_type = {}
        self.__query_parameters = {
            name: value
            for name, value in req.getParameters().items()
            if name not in SPECIAL_QUERY_PARAMETERS }
        self.__resource_name = None
        self.range_accessed = False
        self.context = {}

    def __prepareType(self, resource_type):
        if resource_type not in self.fields_per_type:
            self.fields_per_type[resource_type] = self.req.getParameter(
                "fields[%s]" % resource_type, self.fields,
                filter=lambda value: set(value.split(",")))
        return self.fields_per_type[resource_type]

    def hasField(self, resource_type, key):
        fields = self.__prepareType(resource_type)
        return not fields or key in fields

    def filtered(self, resource_type, resource_json):
        fields = self.__prepareType(resource_type)
        if fields:
            return { key: value
                     for key, value in resource_json.items()
                     if key in fields }
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

    def add(self, resource_type, *ids):
        linked = self.linked_per_type.get(resource_type)
        if linked is not None:
            linked.update(ids)

    def copy(self):
        return copy.deepcopy(self)

HANDLERS = {}

def registerHandler(path, resource_class):
    HANDLERS[path] = resource_class

def PrimaryResource(resource_class):
    assert hasattr(resource_class, "name")
    assert hasattr(resource_class, "value_class")
    if not hasattr(resource_class, "single"):
        resource_class.single = None
    if not hasattr(resource_class, "multiple"):
        resource_class.multiple = None
    if not hasattr(resource_class, "exceptions"):
        resource_class.exceptions = ()
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
        return int(argument)
    except ValueError:
        raise UsageError("Invalid numeric id: %r" % argument)

import v1
import documentation

def handle(critic, req):
    path = req.path.rstrip("/").split("/")

    assert len(path) >= 1 and path.pop(0) == "api"

    if not path:
        documentation.describeRoot()

    api_version = path.pop(0)
    prefix = [api_version]

    if api_version != "v1":
        raise PathError("Unsupported API version: %r" % api_version)

    parameters = Parameters(req)
    linked = Linked(req)

    if not path:
        describe_parameter = parameters.getQueryParameter("describe")
        if describe_parameter:
            v1.documentation.describeResource(describe_parameter)
        v1.documentation.describeVersion()

    context = None

    while True:
        resource_path = prefix + [path.pop(0)]
        resource_class = lookup(resource_path)

        prefix.append(resource_class.name)

        value = None
        values = None

        resource_id = "/".join(resource_path)

        try:
            if path:
                if not resource_class.single:
                    raise UsageError("Resource does not support arguments: %s"
                                     % resource_id)
                arguments = filter(None, path.pop(0).split(","))
                if len(arguments) == 0 or (len(arguments) > 1 and path):
                    raise UsageError("Invalid resource path: %s" % req.path)
                if len(arguments) == 1:
                    with parameters.forResource(resource_class):
                        value = resource_class.single(critic, arguments[0],
                                                      parameters)
                    if not path:
                        break
                    else:
                        assert isinstance(value, resource_class.value_class)
                else:
                    with parameters.forResource(resource_class):
                        values = [resource_class.single(critic, argument,
                                                        parameters)
                                  for argument in arguments]
                    break
            else:
                if not resource_class.multiple:
                    raise UsageError("Resource requires an argument: %s"
                                     % resource_id)
                with parameters.forResource(resource_class):
                    values = resource_class.multiple(critic, parameters)
                if isinstance(values, resource_class.value_class):
                    value, values = values, None
                elif not parameters.range_accessed:
                    begin, end = parameters.getRange()
                    values = itertools.islice(values, begin, end)
                break
        except resource_class.exceptions as error:
            raise PathError("Resource not found: %s" % error.message)

    if values:
        resource_json = {
            resource_class.name: [resource_class.json(value, parameters, linked)
                                  for value in values] }
    else:
        resource_json = resource_class.json(value, parameters, linked)

    if linked.linked_per_type:
        all_linked = linked.copy()

        linked_json = resource_json["linked"] = {
            resource_type: []
            for resource_type in linked.linked_per_type }

        while not linked.isEmpty():
            additional_linked = Linked(req)

            for resource_type, ids in linked.linked_per_type.items():
                resource_class = lookup([api_version, resource_type])

                for resource_id in ids:
                    if isinstance(resource_id, resource_class.value_class):
                        linked_value = resource_id
                    else:
                        linked_value = resource_class.single(
                            critic, resource_id, parameters)

                    linked_json[resource_type].append(resource_class.json(
                        linked_value, parameters, additional_linked))

            for resource_type in linked.linked_per_type.keys():
                additional_linked[resource_type] -= all_linked[resource_type]
                all_linked[resource_type] |= linked[resource_type]

            linked = additional_linked

    return resource_json
