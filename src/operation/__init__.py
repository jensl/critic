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

import sys
import traceback

import base
import mailutils
import dbutils
import htmlutils
import configuration

from textutils import json_encode, json_decode

class OperationResult:
    """\
    Simple container for successful operation result.

    The constructor builds a dictionary from all keyword arguments,
    and adds {"status": "ok"} unless a different "status" is specified
    as a keyword argument.

    Converting an OperationResult object to string converts this
    dictionary to a JSON object literal.
    """

    def __init__(self, **kwargs):
        self.__value = kwargs
        if "status" not in self.__value:
            self.__value["status"] = "ok"
        self.__cookies = {}
    def __str__(self):
        return json_encode(self.__value)
    def set(self, key, value):
        self.__value[key] = value
    def setCookie(self, name, value=None, secure=False):
        self.__cookies[name] = (value, secure)
        return self
    def addResponseHeaders(self, req):
        for name, (value, secure) in self.__cookies.items():
            if value:
                if secure and configuration.base.ACCESS_SCHEME != "http":
                    modifier = "Secure"
                else:
                    modifier = "HttpOnly"
                cookie = "%s=%s; Max-Age=31536000; %s" % (name, value, modifier)
            else:
                cookie = "%s=invalid; Expires=Thursday 01-Jan-1970 00:00:00 GMT" % name
            req.addResponseHeader("Set-Cookie", cookie)

class OperationError(Exception):
    """\
    Exception class for unexpected operation errors.

    Converting an OperationError object to string produces a JSON
    object literal with the properties status="error" and
    error=<message>.
    """

    def __init__(self, message):
        self.__message = message
    def __str__(self):
        return json_encode({ "status": "error", "error": self.__message })

class OperationFailure(Exception):
    """\
    Exception class for operation failures caused by invalid input.

    Converting an OperationError object to string produces a JSON
    object literal with the properties status="failure", title=<title>
    and message=<message>.
    """

    def __init__(self, code, title, message, is_html=False):
        self.__code = code
        self.__title = htmlutils.htmlify(title)
        self.__message = message if is_html else htmlutils.htmlify(message)
    def __str__(self):
        return json_encode({ "status": "failure",
                             "code": self.__code,
                             "title": self.__title,
                             "message": self.__message })

class OperationFailureMustLogin(OperationFailure):
    def __init__(self):
        super(OperationFailureMustLogin, self).__init__(
            "mustlogin",
            "Login Required",
            "You have to sign in to perform this operation.")

class TypeChecker:
    """\
    Interface for checking operation input type correctness.

    Sub-classes implement the method __call__(value, context) which raises an
    OperationError if the input is incorrect.

    A type checker structure is created using the static make() function.

    """
    @staticmethod
    def make(source):
        """\
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
        if type(source) is dict: return DictionaryChecker(source)
        elif type(source) is list: return ArrayChecker(source)
        elif type(source) is set:
            if len(filter(lambda x: type(x) is str, source)) == len(source):
                return EnumerationChecker(source)
            return VariantChecker(source)
        elif source is str: return StringChecker()
        elif source is int: return IntegerChecker()
        elif source is bool: return BooleanChecker()
        else: raise base.ImplementationError("invalid source type")

class Optional:
    """\
    Utility class for signaling that a dictionary member is optional.

    """
    def __init__(self, source):
        self.source = source

class DictionaryChecker:
    """\
    Type checker for dictionary objects.

    Checks two sets of members: required and optional.  Raises an OperationError
    if the checked value is not a dictionary or if any required member is not
    present in it, or if it contains any unexpected members.  Applies
    per-element checkers on all required members and on all present optional
    members.

    """
    def __init__(self, source):
        self.__required = []
        self.__optional = []
        self.__expected = set()

        for name, source_type in source.items():
            if isinstance(source_type, Optional):
                self.__optional.append((name, TypeChecker.make(source_type.source)))
            else:
                self.__required.append((name, TypeChecker.make(source_type)))
            self.__expected.add(name)

    def __call__(self, value, context=None):
        if not type(value) is dict:
            raise OperationError, "invalid input: %s is not a dictionary" % (context if context else "value")
        for name, checker in self.__required:
            child_context = "%s.%s" % (context, name) if context else name
            if name not in value:
                raise OperationError, "invalid input: %s missing" % child_context
            else:
                checker(value[name], child_context)
        for name, checker in self.__optional:
            if name in value:
                child_context = "%s.%s" % (context, name) if context else name
                checker(value[name], child_context)
        for name in value:
            if name not in self.__expected:
                child_context = "%s.%s" % (context, name) if context else name
                raise OperationError, "invalid input: %s is unexpected" % child_context

class ArrayChecker:
    """\
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
            raise OperationError, "%s is not a list" % context
        for index, item in enumerate(value):
            self.__checker(item, "%s[%d]" % (context, index))

class VariantChecker:
    """\
    Type checker for variants (values of one of a set of types.)

    Raises an OperationError if the checked value is not one of the permitted
    types (checked by applying a per-type checker on the value.)

    """
    def __init__(self, source):
        self.__checkers = [TypeChecker.make(item) for item in source]

    def __call__(self, value, context):
        for checker in self.__checkers:
            try:
                checker(value, context)
                return
            except OperationError:
                pass
        raise OperationError("%s is of invalid type" % context)

class EnumerationChecker:
    """\
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
            raise OperationError, "invalid input: %s is not valid" % context

class StringChecker:
    """\
    Type checker for strings.

    Raises an OperationError if the checked value is not a string.

    """
    def __call__(self, value, context):
        if not (type(value) is str or type(value) is unicode):
            raise OperationError, "invalid input: %s is not a string" % context

class IntegerChecker:
    """\
    Type checker for integers.

    Raises an OperationError if the checked value is not an integer.

    """
    def __call__(self, value, context):
        if not type(value) is int:
            raise OperationError, "invalid input: %s is not an integer" % context

class BooleanChecker:
    """\
    Type checker for booleans.

    Raises an OperationError if the checked value is not a boolean.

    """
    def __call__(self, value, context):
        if not type(value) is bool:
            raise OperationError, "invalid input: %s is not a boolean" % context

class Operation(object):
    """\
    Base class for operation implementations.

    Sub-classes  must call Operation.__init__() to define the structure of
    expected input data.

    An operation accepts input in the form of a JSON object literal and returns
    a result in the form of a JSON object literal.  The object contains a
    property named "status" whose value should be "ok" or "error".  If it is
    "error", the object contains a property named "error" whose value is an
    error message.  If the HTTP request method is POST, the input is the request
    body (this is the usual case) otherwise, if the HTTP request method is GET,
    the input is the value of the "data" URI query parameter (this is supported
    to simplify ad-hoc testing).

    Operation implementations should inherit this class and implement the
    process() method.  This method is called with two positional arguments, 'db'
    and 'user', and one keyword argument per property in the input value.  The
    process() method should return an OperationResult object or either return or
    raise an OperationError object.  Any other raised exceptions are caught and
    converted to OperationError objects.

    """
    def __init__(self, parameter_types, accept_anonymous_user=False):
        """\
        Initialize input data type checker.

        The parameter_types argument must be a dict object.  See TypeChecker and
        sub-classes for details on how it works.  A parameter types argument of

          { "name": str,
            "points": [{"x": int, "y": int }],
            "what": Optional(str) }

        would for instance represents an input object with two required
        properties named "name" and "points", and an optional property named
        "what".  The "name" and "what" property values should be a strings.  The
        "points" property value should be an array of objects, each with two
        properties named "x" and "y", whose values should be integer.

        The operation's process() method would be called with the keyword
        arguments "name", "points" and "what".

        """
        if not type(parameter_types) is dict:
            raise base.ImplementationError("invalid source type")
        self.__checker = TypeChecker.make(parameter_types)
        self.__accept_anonymous_user = accept_anonymous_user

    def __call__(self, req, db, user):
        if user.isAnonymous() and not self.__accept_anonymous_user:
            return OperationFailureMustLogin()

        if req.method == "POST": data = req.read()
        else: data = req.getParameter("data")

        if not data: raise OperationError, "no input"

        try: value = json_decode(data)
        except ValueError, error: raise OperationError, "invalid input: %s" % str(error)

        try:
            self.__checker(value)
            return self.process(db, user, **value)
        except OperationError as error:
            return error
        except OperationFailure as failure:
            return failure
        except dbutils.NoSuchUser as error:
            return OperationFailure(code="nosuchuser",
                                    title="Who is '%s'?" % error.name,
                                    message="There is no user in Critic's database named that.")
        except dbutils.NoSuchReview as error:
            return OperationFailure(code="nosuchreview",
                                    title="Invalid review ID" % error.name,
                                    message="The review ID r/%d is not valid." % error.id)
        except dbutils.TransactionRollbackError:
            return OperationFailure(code="transactionrollback",
                                    title="Transaction rolled back",
                                    message="Your database transaction rolled back, probably due to a deadlock.  Please try again.")
        except:
            error_message = ("User: %s\nReferrer: %s\nData: %s\n\n%s"
                             % (user.name,
                                req.getReferrer(),
                                json_encode(self.sanitize(value), indent=2),
                                traceback.format_exc()))

            db.rollback()

            if not user.hasRole(db, "developer"):
                mailutils.sendExceptionMessage("wsgi[%s]" % req.path, error_message)

            if configuration.base.IS_DEVELOPMENT or user.hasRole(db, "developer"):
                return OperationError(error_message)
            else:
                return OperationError("An unexpected error occurred.  " +
                                      "A message has been sent to the system administrator(s) " +
                                      "with details about the problem.")

    def process(self, db, user, **kwargs):
        raise OperationError, "not implemented!?!"

    def sanitize(self, value):
        """Sanitize arguments value for use in error messages or logs."""
        return value

    @staticmethod
    def requireRole(db, role, user):
        if not user.hasRole(db, role):
            raise OperationFailure(
                code="notallowed",
                title="Not allowed!",
                message="Operation not permitted.")
