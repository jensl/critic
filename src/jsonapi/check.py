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
    def __init__(self, parameters):
        self.critic = parameters.critic
        self.__repository = parameters.context.get("repositories")
        self.__review = parameters.context.get("reviews")
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

    @property
    def review(self):
        return self.__review

    @review.setter
    def review(self, review):
        assert self.__review is None or self.__review == review
        self.__review = review
        if review is not None:
            self.repository = review.repository

    @property
    def repository(self):
        return self.__repository

    @repository.setter
    def repository(self, repository):
        assert self.__repository is None or self.__repository == repository
        self.__repository = repository

class TypeChecker(object):
    convert_exception = ()

    def check_compatibility(self, context, value):
        if hasattr(self, "required_isinstance"):
            return isinstance(value, self.required_isinstance)
        return True

    def __call__(self, context, value):
        if not self.check_compatibility(context, value):
            raise jsonapi.InputError("%s: expected %s" % (context, self))
        message = self.check(context, value)
        if message is not None:
            raise jsonapi.InputError("%s: %s" % (context, message))
        if hasattr(self, "convert"):
            try:
                value = self.convert(context, value)
            except self.convert_exception as error:
                raise jsonapi.InputError("%s: %s" % (context, error.message))
        if hasattr(self, "process"):
            self.process(context, value)
        return value

    def __str__(self):
        return self.expected_type

    def check(self, context, value):
        pass

    @staticmethod
    def make(value):
        if ishashable(value) and value in CHECKER_MAP:
            value = CHECKER_MAP[value]
        if isinstance(value, TypeChecker):
            return value
        if isinstance(value, type) and issubclass(value, TypeChecker):
            return value()
        if isinstance(value, list):
            assert(len(value) == 1)
            return ListChecker(value[0])
        if isinstance(value, (set, frozenset, tuple)):
            if all(isinstance(item, str) for item in value):
                return EnumerationChecker(*value)
            return VariantChecker(value)
        if isinstance(value, dict):
            return ObjectChecker(value)
        raise Exception("invalid checked type: %r" % value)

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
    def __init__(self, checkers=None):
        if checkers is None:
            checkers = self.types
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
        self.prioritized = set()
        for attribute_name, attribute_type in attributes.items():
            required = False
            default = False
            if attribute_name.endswith("=null"):
                default = True
                attribute_name = attribute_name[:-5]
            elif attribute_name.endswith("?"):
                attribute_name = attribute_name[:-1]
            else:
                required = True
            if attribute_name.endswith("!"):
                attribute_name = attribute_name[:-1]
                self.prioritized.add(attribute_name)
            self.attributes[attribute_name] = (required, default,
                                               TypeChecker.make(attribute_type))

    def convert(self, context, value):
        result = {}
        def convert_attributes(attributes):
            for attribute_name, attribute_value in attributes:
                with context.push(attribute_name):
                    if attribute_name not in self.attributes:
                        raise jsonapi.InputError(
                            "%s: unexpected attribute" % context)
                    result[attribute_name] = self.attributes[attribute_name][2](
                        context, attribute_value)
        convert_attributes((attribute_name, attribute_value)
                           for attribute_name, attribute_value in value.items()
                           if attribute_name in self.prioritized)
        convert_attributes((attribute_name, attribute_value)
                           for attribute_name, attribute_value in value.items()
                           if attribute_name not in self.prioritized)
        for attribute_name, (required, default, _) in self.attributes.items():
            if attribute_name not in result:
                if required:
                    with context.push(attribute_name):
                        raise jsonapi.InputError("%s: missing attribute"
                                                 % context)
                elif default:
                    result[attribute_name] = None
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
        return super(RestrictedInteger, self).check(context, value)

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
        return super(RestrictedString, self).check(context, value)

class RegularExpression(StringChecker):
    def check(self, context, value):
        try:
            re.compile(value)
        except re.error:
            return "must be a valid Python regular expression"
        return super(RegularExpression, self).check(context, value)

class EnumerationChecker(StringChecker):
    def __init__(self, *values):
        self.values = frozenset(values)

    def check(self, context, value):
        if value not in self.values:
            values = sorted(self.values)
            return ("must be one of %s and %s"
                    % (", ".join(values[:-1]), values[-1]))
        return super(EnumerationChecker, self).check(context, value)

class BoolChecker(TypeChecker):
    required_isinstance = bool
    expected_type = "bool"

class UserId(PositiveInteger):
    convert_exception = api.user.InvalidUserId
    def convert(self, context, value):
        return api.user.fetch(context.critic, user_id=value)

class UserName(StringChecker):
    convert_exception = api.user.InvalidUserName
    def convert(self, context, value):
        return api.user.fetch(context.critic, name=value)

class User(VariantChecker):
    types = (UserId, UserName)

class RepositoryId(PositiveInteger):
    convert_exception = api.repository.InvalidRepositoryId
    def convert(self, context, value):
        return api.repository.fetch(context.critic, repository_id=value)

class RepositoryName(StringChecker):
    convert_exception = api.repository.InvalidRepositoryName
    def convert(self, context, value):
        return api.repository.fetch(context.critic, name=value)

class Repository(VariantChecker):
    types = (RepositoryId, RepositoryName)
    def process(self, context, repository):
        context.repository = repository

    class Required(TypeChecker):
        def check(self, context, value):
            if context.repository is None:
                return "no repository set in context"
            return super(Repository.Required, self).check(context, value)

class Review(PositiveInteger):
    convert_exception = api.review.InvalidReviewId
    def convert(self, context, value):
        return api.review.fetch(context.critic, review_id=value)
    def process(self, context, review):
        context.review = review

class Comment(PositiveInteger):
    convert_exception = api.comment.InvalidCommentId
    def convert(self, context, value):
        return api.comment.fetch(context.critic, comment_id=value)
    def process(self, context, comment):
        context.review = comment.review

class Reply(PositiveInteger):
    convert_exception = api.reply.InvalidReplyId
    def convert(self, context, value):
        return api.reply.fetch(context.critic, reply_id=value)

class CommitId(PositiveInteger):
    convert_exception = api.commit.InvalidCommitId
    def convert(self, context, value):
        return api.commit.fetch(context.repository, commit_id=value)

class CommitReference(StringChecker):
    convert_exception = api.repository.InvalidRef
    def convert(self, context, value):
        return api.commit.fetch(context.repository, ref=value)

class Commit(VariantChecker, Repository.Required):
    types = (CommitId, CommitReference)

class FileId(PositiveInteger):
    convert_exception = api.file.InvalidFileId
    def convert(self, context, value):
        return api.file.fetch(context.critic, file_id=value)

class FilePath(StringChecker):
    convert_exception = api.file.InvalidPath
    def convert(self, context, value):
        return api.file.fetch(context.critic, path=value)

class File(VariantChecker):
    types = (FileId, FilePath)

class Changeset(PositiveInteger, Repository.Required):
    convert_exception = api.changeset.InvalidChangesetId
    def convert(self, context, value):
        assert context.repository
        return api.changeset.fetch(context.critic, context.repository, id=value)

class ExtensionId(PositiveInteger):
    convert_exception = api.extension.InvalidExtensionId
    def convert(self, context, value):
        return api.extension.fetch(context.critic, extension_id=value)

class ExtensionKey(StringChecker):
    convert_exception = api.extension.InvalidExtensionKey
    def convert(self, context, value):
        return api.extension.fetch(context.critic, key=value)

class Extension(VariantChecker):
    types = (ExtensionId, ExtensionKey)

class AccessControlProfile(PositiveInteger):
    convert_exception = api.accesscontrolprofile.InvalidAccessControlProfileId
    def convert(self, context, value):
        return api.accesscontrolprofile.fetch(context.critic, profile_id=value)

CHECKER_MAP = { int: IntegerChecker(),
                str: StringChecker(),
                bool: BoolChecker(),
                api.user.User: User,
                api.repository.Repository: Repository,
                api.review.Review: Review,
                api.comment.Comment: Comment,
                api.reply.Reply: Reply,
                api.commit.Commit: Commit,
                api.file.File: File,
                api.changeset.Changeset: Changeset,
                api.extension.Extension: Extension,
                api.accesscontrolprofile.AccessControlProfile:
                    AccessControlProfile }

def convert(parameters, checker, value):
    context = TypeCheckerContext(parameters)
    return TypeChecker.make(checker)(context, value)

def ensure(data, path, ensured_value):
    if isinstance(path, (tuple, list)):
        for key in path[:-1]:
            data = data[key]
        key = path[-1]
    else:
        key = path

    if key not in data:
        data[key] = ensured_value
    elif data[key] != ensured_value:
        path_string = "data"
        for key in path:
            if isinstance(key, str):
                path_string += "." + key
            else:
                path_string += "[%d]" % key
        raise jsonapi.InputError("%s: must be %r or omitted"
                                 % (path_string, ensured_value))
