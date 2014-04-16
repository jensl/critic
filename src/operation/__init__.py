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

import traceback

import base
import dbutils
import extensions

from textutils import json_encode, json_decode

from operation.basictypes import (OperationResult, OperationError,
                                  OperationFailure, OperationFailureMustLogin)

from operation.typechecker import (Optional, Request, RestrictedString, SHA1,
                                   RestrictedInteger, NonNegativeInteger,
                                   PositiveInteger, Review, Repository, Commit,
                                   File, User, Extension)

class Operation(object):

    """
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
        """
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
        from operation.typechecker import TypeChecker
        if not type(parameter_types) is dict:
            raise base.ImplementationError("invalid source type")
        self.__checker = TypeChecker.make(parameter_types)
        self.__accept_anonymous_user = accept_anonymous_user

    def __call__(self, req, db, user):
        from operation.typechecker import TypeCheckerContext

        if user.isAnonymous() and not self.__accept_anonymous_user:
            return OperationFailureMustLogin()

        if req.method == "POST": data = req.read()
        else: data = req.getParameter("data")

        if not data: raise OperationError("no input")

        try: value = json_decode(data)
        except ValueError as error: raise OperationError("invalid input: %s" % str(error))

        try:
            self.__checker(value, TypeCheckerContext(req, db, user))
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
                                    title="Invalid review ID",
                                    message="The review ID r/%d is not valid." % error.id)
        except dbutils.TransactionRollbackError:
            return OperationFailure(code="transactionrollback",
                                    title="Transaction rolled back",
                                    message="Your database transaction rolled back, probably due to a deadlock.  Please try again.")
        except extensions.extension.ExtensionError as error:
            return OperationFailure(
                code="invalidextension",
                title="Invalid extension",
                message=error.message)
        except:
            # Decode value again since the type checkers might have modified it.
            value = json_decode(data)

            error_message = ("User: %s\nReferrer: %s\nData: %s\n\n%s"
                             % (user.name,
                                req.getReferrer(),
                                json_encode(self.sanitize(value), indent=2),
                                traceback.format_exc()))

            db.rollback()

            import mailutils
            import configuration

            if not user.hasRole(db, "developer"):
                mailutils.sendExceptionMessage(db, "wsgi[%s]" % req.path, error_message)

            if configuration.debug.IS_DEVELOPMENT or user.hasRole(db, "developer"):
                return OperationError(error_message)
            else:
                return OperationError("An unexpected error occurred.  " +
                                      "A message has been sent to the system administrator(s) " +
                                      "with details about the problem.")

    def process(self, *args, **kwargs):
        raise OperationError("not implemented!?!")

    def sanitize(self, value):
        """Sanitize arguments value for use in error messages or logs."""
        return value

    @staticmethod
    def requireRole(db, role, user):
        if not user.hasRole(db, role):
            raise OperationFailure(
                code="notallowed",
                title="Not allowed!",
                message="Operation not permitted, user that lacks role '%s'." % role)
