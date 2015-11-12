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

import contextlib
import re

import api
import jsonapi

def ishashable(value):
    try:
        hash(value)
    except TypeError:
        return False
    else:
        return True

class TypeCheckerContext(object):
    def __init__(self, critic):
        self.critic = critic
        self.repository = None
        self.review = None
        self.__path = ["data"]

    @contextlib.contextmanager
    def push(self, element):
        if isinstance(element, int):
            self.__path.append("[%d]" % element)
        else:
            self.__path.append("." + str(element))
        yield
        self.__path.pop()

    def __str__(self):
        return "".join(self.__path)

class TypeChecker(object):
    convert_exception = ()

    def check_compatibility(self, context, value):
        if hasattr(self, "required_isinstance"):
            return isinstance(value, self.required_isinstance)
        return True

    def __call__(self, context, value):
        if not self.check_compatibility(context, value):
            raise jsonapi.InputError("%s: expected %s" % (context, self))
        if hasattr(self, "check"):
            message = self.check(context, value)
            if message is not None:
                raise jsonapi.InputError("%s: %s" % (context, message))
        if hasattr(self, "convert"):
            try:
                value = self.convert(context, value)
            except self.convert_exception as error:
                raise jsonapi.InputError("%s: %s" % (context, error.message))
        return value

    def __str__(self):
        return self.expected_type

    @staticmethod
    def make(value):
        if isinstance(value, TypeChecker):
            return value
        elif isinstance(value, type) and issubclass(value, TypeChecker):
            return value()
        elif ishashable(value) and value in CHECKER_MAP:
            return CHECKER_MAP[value]
        elif isinstance(value, list):
            assert(len(value) == 1)
            return ListChecker(value[0])
        elif isinstance(value, set):
            if all(isinstance(item, str) for item in value):
                return EnumerationChecker(*value)
            return VariantChecker(*value)
        elif isinstance(value, dict):
            return ObjectChecker(value)

class ListChecker(TypeChecker):
    required_isinstance = list

    def __init__(self, checker):
        self.checker = TypeChecker.make(checker)
        self.expected_type = "list of %s" % self.checker.expected_type

    def convert(self, context, value):
        result = []
        for index, element in enumerate(value):
            with context.push(index):
                result.append(self.checker(context, element))
        return result

class VariantChecker(TypeChecker):
    def __init__(self, *checkers):
        self.checkers = map(TypeChecker.make, checkers)
        self.matched = None
        self.expected_type = "%s or %s" % (", ".join(map(str, self.checkers[:-1])),
                                           self.checkers[-1])

    def check_compatibility(self, context, value):
        for checker in self.checkers:
            if checker.check_compatibility(context, value):
                self.matched = checker
                self.convert_exception = checker.convert_exception
                return True
        return False

    def convert(self, context, value):
        try:
            return self.matched(context, value)
        finally:
            self.matched = None

class ObjectChecker(TypeChecker):
    required_isinstance = dict
    expected_type = "object"

    def __init__(self, attributes):
        self.attributes = {}
        for attribute_name, attribute_type in attributes.items():
            if attribute_name.endswith("?"):
                required = False
                attribute_name = attribute_name[:-1]
            else:
                required = True
            self.attributes[attribute_name] = (required,
                                               TypeChecker.make(attribute_type))

    def convert(self, context, value):
        result = {}
        for attribute_name, attribute_value in value.items():
            with context.push(attribute_name):
                if attribute_name not in self.attributes:
                    raise jsonapi.InputError(
                        "%s: unexpected attribute" % context)
                result[attribute_name] = self.attributes[attribute_name][1](
                    context, attribute_value)
        for attribute_name, (required, _) in self.attributes.items():
            if required and attribute_name not in result:
                with context.push(attribute_name):
                    raise jsonapi.InputError(
                        "%s: missing attribute" % context)
        return result

class IntegerChecker(TypeChecker):
    required_isinstance = int
    expected_type = "integer"

class RestrictedInteger(IntegerChecker):
    def __init__(self, minvalue=None, maxvalue=None):
        self.minvalue = minvalue
        self.maxvalue = maxvalue

    def check(self, context, value):
        if self.minvalue is not None and value < self.minvalue:
            return "must be at least %d" % self.minvalue
        if self.maxvalue is not None and value > self.maxvalue:
            return "can be at most %d" % self.maxvalue

class NonNegativeInteger(RestrictedInteger):
    def __init__(self):
        super(NonNegativeInteger, self).__init__(minvalue=0)

class PositiveInteger(RestrictedInteger):
    def __init__(self):
        super(PositiveInteger, self).__init__(minvalue=1)

class StringChecker(TypeChecker):
    required_isinstance = basestring
    expected_type = "string"

class RestrictedString(StringChecker):
    def __init__(self, minlength=None, maxlength=None, regexp=None):
        self.minlength = minlength
        self.maxlength = maxlength
        self.regexp = re.compile(regexp) if regexp else None

    def check(self, context, value):
        if self.minlength is not None and len(value) < self.minlength:
            return "must be at least %d characters long" % self.minlength
        if self.maxlength is not None and len(value) < self.maxlength:
            return "can be at most %d characters long" % self.maxlength
        if self.regexp is not None and not self.regexp.match(value):
            return "must match '%s'" % self.regexp.pattern

class RegularExpression(StringChecker):
    def check(self, context, value):
        try:
            re.compile(value)
        except re.error:
            return "must be a valid Python regular expression"

class EnumerationChecker(StringChecker):
    def __init__(self, *values):
        self.values = frozenset(values)

    def check(self, context, value):
        if value not in self.values:
            values = sorted(self.values)
            return ("must be one of %s and %s"
                    % (", ".join(values[:-1]), values[-1]))

class UserId(PositiveInteger):
    convert_exception = api.user.InvalidUserId
    def convert(self, context, value):
        return api.user.fetch(context.critic, user_id=value)

class UserName(StringChecker):
    convert_exception = api.user.InvalidUserName
    def convert(self, context, value):
        return api.user.fetch(context.critic, name=value)

class User(VariantChecker):
    def __init__(self):
        super(User, self).__init__(UserId, UserName)

class RepositoryId(PositiveInteger):
    convert_exception = api.repository.InvalidRepositoryId
    def convert(self, context, value):
        return api.repository.fetch(context.critic, repository_id=value)

class RepositoryName(StringChecker):
    convert_exception = api.repository.InvalidRepositoryName
    def convert(self, context, value):
        return api.repository.fetch(context.critic, name=value)

class Repository(VariantChecker):
    def __init__(self):
        super(Repository, self).__init__(RepositoryId, RepositoryName)

class ExtensionId(PositiveInteger):
    convert_exception = api.extension.InvalidExtensionId
    def convert(self, context, value):
        return api.extension.fetch(context.critic, extension_id=value)

class ExtensionKey(StringChecker):
    convert_exception = api.extension.InvalidExtensionKey
    def convert(self, context, value):
        return api.extension.fetch(context.critic, key=value)

class Extension(VariantChecker):
    def __init__(self):
        super(Extension, self).__init__(ExtensionId, ExtensionKey)

CHECKER_MAP = { int: IntegerChecker(),
                str: StringChecker(),
                api.user.User: User(),
                api.repository.Repository: Repository(),
                api.extension.Extension: Extension() }

def convert(parameters, checker, value):
    context = TypeCheckerContext(parameters.critic)
    return TypeChecker.make(checker)(context, value)
