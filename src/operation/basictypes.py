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

import htmlutils
import textutils

class OperationResult:

    """
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
        return textutils.json_encode(self.__value)
    def set(self, key, value):
        self.__value[key] = value

class OperationError(Exception):

    """
    Exception class for unexpected operation errors.

    Converting an OperationError object to string produces a JSON
    object literal with the properties status="error" and
    error=<message>.
    """

    def __init__(self, message):
        self.__message = message
    def __str__(self):
        return textutils.json_encode({ "status": "error",
                                       "error": self.__message })

class OperationFailure(Exception):

    """
    Exception class for operation failures caused by invalid input.

    Converting an OperationFailure object to string produces a JSON
    object literal with the properties status="failure", title=<title>
    and message=<message>.
    """

    def __init__(self, code, title, message, is_html=False):
        self.__code = code
        self.__title = htmlutils.htmlify(title)
        self.__message = message if is_html else htmlutils.htmlify(message)
    def __str__(self):
        return textutils.json_encode({ "status": "failure",
                                       "code": self.__code,
                                       "title": self.__title,
                                       "message": self.__message })

class OperationFailureMustLogin(OperationFailure):
    def __init__(self):
        super(OperationFailureMustLogin, self).__init__(
            code="mustlogin",
            title="Login Required",
            message="You have to sign in to perform this operation.")
