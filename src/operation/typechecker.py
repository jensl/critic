# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 Jens Lindström, Opera Software ASA
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

import re

import base
import dbutils

from operation.basictypes import OperationError, OperationFailure

class Optional:

    """Utility class for signaling that a dictionary member is optional."""

    def __init__(self, source):
        self.source = source

class TypeCheckerContext(object):
    def __init__(self, *args):
        self.args = args
        self.req, self.db, self.user = args
        self.repository = None
        self.review = None
        self.__path = ["data"]
    def __str__(self):
        return "".join(self.__path)
    def push(self, name):
        self.__path.append(name)
    def pop(self):
        self.__path.pop()
    def clone(self):
        copy = TypeCheckerContext(*self.args)
        copy.copy_from(self)
        copy.__path = self.__path[:]
        return copy
    def copy_from(self, other):
        self.repository = other.repository
        self.review = other.review

class TypeChecker(object):

    """
    Interface for checking operation input type correctness.

    Sub-classes implement the method __call__(value, context) which raises an
    OperationError if the input is incorrect.

    A type checker structure is created using the static make() function.
    """

    @staticmethod
    def make(source):
        """
        Construct a structure of TypeChecker objects.

        The source argument should be a dict object, single-element list object,
        a set object containing strings, or str, int or bool (the actual type
        objects, not a string, integer or boolean value).

        If the source argument is a dict object, per-element type checkers are
        constructed by calling this function on the value of each item in the
        dictionary.  See DictionaryChecker for details.

        If the source argument is a list object, a per-element type checker is
        constructed by calling this function on the value of the single element
        in the list.

        If the source argument is a set object, all elements in it should be
        strings, and the constructed checker verifies that the value is a string
        that is a member of the set.

        Otherwise the constructed checker verifies that the value is of the type
        of the source argument (or, in the case of source=str, that the value's
        type is either str or unicode).
        """

        if isinstance(source, TypeChecker):
            return source
        elif isinstance(source, dict):
            return DictionaryChecker(source)
        elif isinstance(source, list):
            return ArrayChecker(source)
        elif isinstance(source, set):
            if all(type(x) is str for x in source):
                return EnumerationChecker(source)
            return VariantChecker(source)
        elif source is str:
            return StringChecker()
        elif source is int:
            return IntegerChecker()
        elif source is bool:
            return BooleanChecker()

        try:
            is_type_checker = issubclass(source, TypeChecker)
        except TypeError:
            pass
        else:
            if is_type_checker:
                return source()

        raise base.ImplementationError("invalid source type: %s" % type(source))

    def getSuffixedCheckers(self):
        """
        Return a list of (suffix, checker) tuples.

        A suffixed checker allows a parameter to be specified with an optional
        suffix, that (optionally) restricts the acceptable input values.  For
        instance, a checker that supports either an integer id or a string name
        could return a list

          [("id", id_checker), ("name", name_checker)]

        with the effect that the input can be one of

          { "thing": id-or-name }
          { "thing_id": id }
          { "thing_name": name }

        and the resulting parameter name "thing" in either case.

        A checker can also return [("suffix", None)] to signal that a suffix is
        supported, but that the same checker (not a restricted one) should be
        applied regardless.
        """
        return []

class Implicit(object):

    """
    Mix-in class for implicit parameters.

    An implicit parameter is one we don't expect to receive from the client at
    all, but rather already have.  The use-case is for an operation to request
    additional information passed to it, for instance a reference to the Request
    object.
    """

    pass

class Prioritized(object):

    """
    Mix-in class for prioritized parameters.

    A prioritized parameter is one that stores information in the context that
    might be required for the checkers of other parameters, and thus need to be
    processed first.  DictionaryChecker uses this to control the order in which
    it processes dictionary items.
    """

    pass

class Request(TypeChecker, Implicit):
    def __call__(self, value, context):
        assert value is None
        return context.req

class BooleanChecker(TypeChecker):

    """
    Type checker for booleans.

    Raises an OperationError if the checked value is not a boolean.
    """

    def __call__(self, value, context):
        if not isinstance(value, bool):
            raise OperationError("invalid input: %s is not a boolean" % context)

class StringChecker(TypeChecker):

    """
    Type checker for strings.

    Raises an OperationError if the checked value is not a string.
    """

    def __call__(self, value, context):
        if not isinstance(value, basestring):
            raise OperationError("invalid input: %s is not a string" % context)

class RestrictedString(StringChecker):

    """
    Type checker for restricted strings.

    A restricted string is one that may consist only of certain characters,
    and/or must be of a certain min/max length.

    Raises an OperationFailure if the checked value is not valid.
    """

    def __init__(self, allowed=None, minlength=None, maxlength=None, ui_name=None):
        self.allowed = allowed
        self.minlength = minlength
        self.maxlength = maxlength
        self.ui_name = ui_name

    def __call__(self, value, context):
        super(RestrictedString, self).__call__(value, context)
        if self.ui_name:
            ui_name = self.ui_name
        else:
            ui_name = context
        if self.minlength is not None \
                and len(value) < self.minlength:
            raise OperationFailure(
                code="paramtooshort:%s" % context,
                title="Invalid %s" % ui_name,
                message=("invalid input: %s must be at least %d characters long"
                         % (ui_name, self.minlength)))
        if self.maxlength is not None \
                and len(value) > self.maxlength:
            raise OperationFailure(
                code="paramtoolong:%s" % context,
                title="Invalid %s" % ui_name,
                message=("invalid input: %s must be at most %d characters long"
                         % (ui_name, self.maxlength)))
        if self.allowed:
            disallowed = [ch for ch in sorted(set(value))
                          if not self.allowed(ch)]
            if disallowed:
                raise OperationFailure(
                    code="paramcontainsillegalchar:%s" % context,
                    title="Invalid %s" % ui_name,
                    message=("invalid input: %s may not contain the character%s %s"
                             % (ui_name, "s" if len(disallowed) > 1 else "",
                                ", ".join(repr(ch) for ch in disallowed))))

class SHA1(RestrictedString):
    def __init__(self):
        super(SHA1, self).__init__(minlength=4,
                                   maxlength=40,
                                   allowed=re.compile("[0-9A-Fa-f]$").match)

class IntegerChecker(TypeChecker):

    """
    Type checker for integers.

    Raises an OperationError if the checked value is not an integer.
    """

    def __call__(self, value, context):
        if not isinstance(value, int) or isinstance(value, bool):
            raise OperationError("invalid input: %s is not an integer" % context)

class RestrictedInteger(IntegerChecker):
    def __init__(self, minvalue=None, maxvalue=None, ui_name=None):
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.ui_name = ui_name

    def __call__(self, value, context):
        super(RestrictedInteger, self).__call__(value, context)
        if self.ui_name:
            ui_name = self.ui_name
        else:
            ui_name = context
        if self.minvalue is not None \
                and value < self.minvalue:
            raise OperationFailure(
                code="valuetoolow:%s" % context,
                title="Invalid %s parameter" % ui_name,
                message=("invalid input: %s must be %d or higher"
                         % (ui_name, self.minvalue)))
        if self.maxvalue is not None \
                and value > self.maxvalue:
            raise OperationFailure(
                code="valuetoohigh:%s" % context,
                title="Invalid %s parameter" % ui_name,
                message=("invalid input: %s must be %d or lower"
                         % (ui_name, self.maxvalue)))

class PositiveInteger(RestrictedInteger):
    def __init__(self):
        super(PositiveInteger, self).__init__(minvalue=1)

def check(checker, value, context):
    """Apply checker and return converted, or original, value."""
    converted = checker(value, context)
    if converted is None:
        return value
    return converted

class DictionaryChecker(TypeChecker):

    """
    Type checker for dictionary objects.

    Checks two sets of members: required and optional.  Raises an OperationError
    if the checked value is not a dictionary or if any required member is not
    present in it, or if it contains any unexpected members.  Applies
    per-element checkers on all required members and on all present optional
    members.
    """

    def __init__(self, source):
        self.__implicit = []
        self.__prioritized = []
        self.__required = []
        self.__optional = []
        self.__expected = set()

        for name, source_type in source.items():
            if isinstance(source_type, Optional):
                checker = TypeChecker.make(source_type.source)
                if isinstance(checker, (Implicit, Prioritized)):
                    raise base.ImplementationError(
                        "implicit/prioritized parameter cannot be optional: %s"
                        % name)
                self.__optional.append((name, checker))
            else:
                checker = TypeChecker.make(source_type)
                if isinstance(checker, Implicit):
                    self.__implicit.append((name, checker))
                elif isinstance(checker, Prioritized):
                    self.__prioritized.append((name, checker))
                else:
                    self.__required.append((name, checker))
            for suffix, _ in checker.getSuffixedCheckers():
                if name.endswith("_" + suffix):
                    raise base.ImplementationError(
                        "invalid parameter name: %s (includes optional suffix)"
                        % name)

    def __call__(self, value, context):
        if not type(value) is dict:
            raise OperationError("invalid input: %s is not a dictionary" % context)

        specified_names = set(value.keys())

        class Missing:
            pass

        def read_with_suffixes(name, checker):
            try:
                if name in value:
                    specified_names.remove(name)
                    context.push("." + name)
                    return check(checker, value[name], context)
                for suffix, suffixed_checker in checker.getSuffixedCheckers():
                    suffixed_name = "%s_%s" % (name, suffix)
                    if suffixed_name in value:
                        specified_names.remove(suffixed_name)
                        context.push("." + suffixed_name)
                        if suffixed_checker is not None:
                            checker = suffixed_checker
                        return check(checker, value.pop(suffixed_name), context)
                context.push("." + name)
                return Missing
            finally:
                context.pop()

        for name, checker in self.__implicit:
            context.push("." + name)
            if name in value:
                raise OperationError(
                    "invalid input: %s should not be specified" % context)
            value[name] = checker(None, context)
            context.pop()

        def process_members(items, required):
            for name, checker in items:
                converted = read_with_suffixes(name, checker)
                if not converted is Missing:
                    value[name] = converted
                elif required:
                    context.push("." + name)
                    raise OperationError("invalid input: %s missing" % context)

        process_members(self.__prioritized, True)
        process_members(self.__required, True)
        process_members(self.__optional, False)

        if specified_names:
            context.push("." + specified_names.pop())
            raise OperationError("invalid input: %s was not used" % context)

class ArrayChecker(TypeChecker):

    """
    Type checker for arrays.

    Raises an OperationError if the checked value is not an array.  Applies the
    per-element checker on each element in the array.
    """

    def __init__(self, source):
        if len(source) != 1:
            raise base.ImplementationError("invalid source type")
        self.__checker = TypeChecker.make(source[0])

    def __call__(self, value, context):
        if not type(value) is list:
            raise OperationError("%s is not a list" % context)
        for index, item in enumerate(value):
            context.push("[%d]" % index)
            value[index] = check(self.__checker, item, context)
            context.pop()

class VariantChecker(TypeChecker):

    """
    Type checker for variants (values of one of a set of types.)

    Raises an OperationError if the checked value is not one of the permitted
    types (checked by applying a per-type checker on the value.)
    """

    def __init__(self, source):
        self.__checkers = []
        self.__suffixed_checkers = []
        if isinstance(source, dict):
            for suffix, item in source.items():
                checker = TypeChecker.make(item)
                self.__checkers.append(checker)
                self.__suffixed_checkers.append((suffix, checker))
        else:
            self.__checkers.extend(TypeChecker.make(item) for item in source)

    def __call__(self, value, context):
        for checker in self.__checkers:
            try:
                variant_context = context.clone()
                value = checker(value, variant_context)
                context.copy_from(variant_context)
                return value
            except (OperationError, OperationFailure):
                pass
        raise OperationError("%s is of invalid type" % context)

    def getSuffixedCheckers(self):
        return self.__suffixed_checkers

class EnumerationChecker(TypeChecker):

    """
    Type checker for enumerations.

    Raises an OperationError if the checked value is not a string or if the
    string value is not a member of the enumeration.
    """

    def __init__(self, source):
        self.__checker = TypeChecker.make(str)
        for item in source:
            if not type(item) is str:
                raise base.ImplementationError("invalid source type")
        self.__enumeration = source

    def __call__(self, value, context):
        self.__checker(value, context)
        if value not in self.__enumeration:
            raise OperationError("invalid input: %s is not valid" % context)

class Review(PositiveInteger, Prioritized):
    def __call__(self, value, context):
        super(Review, self).__call__(value, context)
        context.review = dbutils.Review.fromId(context.db, value)
        context.repository = context.review.repository
        return context.review

    def getSuffixedCheckers(self):
        return [("id", None)]

class RepositoryId(PositiveInteger):
    def __call__(self, value, context):
        import gitutils
        super(RepositoryId, self).__call__(value, context)
        context.repository = gitutils.Repository.fromId(context.db, value)
        return context.repository

class RepositoryName(StringChecker):
    def __call__(self, value, context):
        import gitutils
        super(RepositoryName, self).__call__(value, context)
        context.repository = gitutils.Repository.fromName(context.db, value)
        return context.repository

class Repository(VariantChecker, Prioritized):
    def __init__(self):
        super(Repository, self).__init__({ "id": RepositoryId,
                                           "name": RepositoryName })

class CommitId(PositiveInteger):
    def __call__(self, value, context):
        import gitutils
        if context.repository:
            raise OperationError("missing repository in context")
        super(CommitId, self).__call__(value, context)
        return gitutils.Commit.fromId(context.db, context.repository, value)

class CommitSHA1(SHA1):
    def __call__(self, value, context):
        import gitutils
        if context.repository:
            raise OperationError("missing repository in context")
        super(CommitSHA1, self).__call__(value, context)
        return gitutils.Commit.fromSHA1(context.db, context.repository, value)

class Commit(VariantChecker):
    def __init__(self):
        super(Commit, self).__init__({ "id": CommitId,
                                       "sha1": CommitSHA1 })

    def __call__(self, value, context):
        if context.repository:
            raise OperationError("missing repository in context")
        return super(Commit, self).__call__(value, context)

class FileId(PositiveInteger):
    def __call__(self, value, context):
        super(FileId, self).__call__(value, context)
        return dbutils.File.fromId(context.db, value)

class FilePath(StringChecker):
    def __call__(self, value, context):
        super(FilePath, self).__call__(value, context)
        return dbutils.File.fromPath(context.db, value, insert=False)

class File(VariantChecker):
    def __init__(self):
        super(File, self).__init__({ "id": FileId,
                                     "path": FilePath })

class UserId(PositiveInteger):
    def __call__(self, value, context):
        super(UserId, self).__call__(value, context)
        return dbutils.User.fromId(context.db, value)

class UserName(StringChecker):
    def __call__(self, value, context):
        super(UserName, self).__call__(value, context)
        return dbutils.User.fromName(context.db, value)

class User(VariantChecker):
    def __init__(self):
        super(User, self).__init__({ "id": UserId,
                                     "name": UserName })
