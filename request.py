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

import re
import httplib

import base
import utf8utils
import configuration

def decodeURIComponent(text):
    """\
    Replace %HH escape sequences and return the resulting string.
    """

    return utf8utils.convertUTF8(re.sub("%([0-9A-Fa-f]{2})", lambda match: chr(int(match.group(1), 16)), text))

class NoDefault:
    """\
    Placeholder class to signal that a parameter has no default value.

    An instance of this class is provided to Request.getParameter() as the
    'default' argument to signal that it is an error if the parameter is
    not present.
    """

    pass

class DisplayMessage:
    """\
    Utility exception raised by pages to display a simply message.
    """

    def __init__(self, title, body=None, review=None, html=False):
        self.title = title
        self.body = body
        self.review = review
        self.html = html

class InvalidParameterValue(DisplayMessage):
    """\
    Exception raised by pages when a query parameter has an invalid value.

    This exception is automatically raised by Request.getParameter() if the
    parameter's value can't be converted as requested.
    """

    def __init__(self, name, value, expected):
        DisplayMessage.__init__(self, "Invalid URI Parameter Value!", "Got '%s=%s', expected %s." % (name, value, expected))

class MissingParameter(DisplayMessage):
    """\
    Exception raised by pages when a required query parameter is missing.

    This exception is automatically raised by Request.getParameter() if the
    parameter is required and missing.
    """

    def __init__(self, name):
        DisplayMessage.__init__(self, "Missing URI Parameter!", "Expected '%s' parameter." % name)

class Request:
    """\
    WSGI request wrapper class.

    Pages and operations should typically only need to access request parameters
    (via getParameter()) and headers (via getRequestHeader()), and set response
    status (using setStatus()) if not "200 OK" and content-type (using
    setContentType()) if not "text/html".  The start() method must be called
    before any content is returned to the WSGI layer, but this is taken care of
    by the main request handling function (critic.py::main).

    In the case of POST requests, the request body is retrieved using the read()
    method.

    Properties:

    user -- user name from HTTP authentication
    method -- HTTP method ("GET" or "POST", typically)
    path -- URI path component, without leading forward slash
    original_path -- same as 'path', unless the path is a short-hand for another
                     path, in which case 'path' is the resolved path
    query -- URI query component

    Primary methods:

    getParameter(name, default, filter) -- get URI query parameter
    getRequestHeader(name) -- get HTTP request header
    getRequestHeaders(name) -- get all HTTP request headers
    read() -- read HTTP request body
    setStatus(code, message) -- set HTTP response status
    setContentType(content_type) -- set Content-Type response header
    addResponseHeader(name, value) -- add HTTP response header

    Methods used by framework code:

    start() -- call the WSGI layers start_response() callback
    isStarted() -- check if start() has been called
    getContentType() -- get response content type
    """

    def __init__(self, db, environ, start_response):
        """\
        Construct request wrapper.

        The environ and start_response arguments should be the arguments to the
        WSGI application object.
        """

        self.__environ = environ
        self.__start_response = start_response
        self.__status = None
        self.__content_type = None
        self.__response_headers = []
        self.__started = False

        self.server_name = \
            self.getRequestHeader("X-Forwarded-Host") \
            or environ.get("SERVER_NAME") \
            or configuration.base.HOSTNAME

        self.method = environ.get("REQUEST_METHOD", "")
        self.path = environ.get("PATH_INFO", "").lstrip("/")
        self.original_path = self.path
        self.query = environ.get("QUERY_STRING", "")
        self.user = None

        self.__setUser(db, environ)

    def __setUser(self, db, environ):
        if configuration.base.AUTHENTICATION_MODE == "host":
            self.user = environ.get("REMOTE_USER")
        elif configuration.base.AUTHENTICATION_MODE == "critic":
            if configuration.base.SESSION_TYPE == "cookie":
                header = self.getRequestHeader("Cookie")
                if header:
                    cookies = map(str.strip, header.split(";"))
                    key = None

                    for cookie in cookies:
                        name, value = cookie.split("=", 1)
                        if name == "sid":
                            key = value
                            break

                    if key:
                        cursor = db.cursor()
                        cursor.execute("""SELECT name, EXTRACT('epoch' FROM NOW() - atime) AS age
                                            FROM usersessions
                                            JOIN users ON (id=uid)
                                           WHERE key=%s""",
                                       (key,))

                        try: user, session_age = cursor.fetchone()
                        except: return

                        if configuration.base.SESSION_MAX_AGE == 0 \
                                or session_age < configuration.base.SESSION_MAX_AGE:
                            self.user = user

                            cursor.execute("""UPDATE usersessions
                                                 SET atime=NOW()
                                               WHERE key=%s""",
                                           (key,))
                            db.commit()
            else:
                import auth
                import base64

                self.user = None

                authorization = self.getRequestHeader("Authorization")
                if not authorization: return

                authtype, base64_credentials = authorization.split()
                if authtype != "Basic": return

                credentials = base64.b64decode(base64_credentials).split(":")
                if len(credentials) < 2: return

                for index in range(1, len(credentials)):
                    username = ":".join(credentials[:index])
                    password = ":".join(credentials[index:])
                    try:
                        auth.checkPassword(db, username, password)
                        self.user = username
                        return
                    except auth.CheckFailed: pass

    def getUser(self, db):
        import dbutils
        return dbutils.User.fromName(db, self.user)

    def getParameter(self, name, default=NoDefault(), filter=lambda value: value):
        """\
        Get URI query parameter.

        If the requested parameter was not present in the URI query component,
        the supplied default value is returned instead, or, if the supplied
        default value is an instance of the NoDefault class, a MissingParameter
        exception is raised.

        If a filter function is supplied, it is called with a single argument,
        the string value of the URI parameter, and its return value is returned
        from getParameter().  If the filter function raises an exception (other
        than DisplayMessage or sub-classes thereof) an InvalidParameterValue
        exception is raised.  Note: the filter function is not applied to
        default values, meaning that the default value can be of a different
        type than actual parameter values.
        """

        match = re.search("(?:^|&)" + name + "=([^&]*)", str(self.query))
        if match:
            try: return filter(decodeURIComponent(match.group(1)))
            except DisplayMessage: raise
            except base.Error: raise
            except:
                if filter is int: expected = "expected integer"
                else: expected = "something else"
                raise InvalidParameterValue, (name, match.group(1), expected)
        elif isinstance(default, NoDefault): raise MissingParameter, name
        else: return default

    def getRequestHeader(self, name):
        """\
        Get HTTP request header by name.

        The name is case-insensitive.  If the request header was not present in
        the request, None is returned, otherwise the header's value is returned
        as a string.
        """

        return self.__environ.get("HTTP_" + name.upper().replace("-", "_"))

    def getRequestHeaders(self):
        """\
        Get a dictionary containing all HTTP request headers.

        The header names are converted to all lower-case, and any underscores
        ('_') in the header name is replaced with a dash ('-').  The reason for
        this name transformation is that the header names are already
        transformed in the WSGI layer from their original form to all
        upper-case, with dashes replaced by underscores, so the original name is
        not available.

        The returned dictionary is a copy of the underlying storage, so the
        caller can modify it without the modifications having any side-effects.
        """

        headers = {}
        for name, value in self.__environ.items():
            if name.startswith("HTTP_"):
                headers[name[5:].lower().replace("_", "-")] = value
        return headers

    def getReferrer(self):
        try: return self.getRequestHeader("Referer")
        except: return "N/A"

    def read(self):
        """\
        Return the HTTP request body, or an empty string if there is none.
        """

        if "wsgi.input" not in self.__environ: return ""
        return self.__environ["wsgi.input"].read()

    def setStatus(self, code, message=None):
        """\
        Set the HTTP status code, and optionally the status message.

        If the message argument is None, a default status message for the
        specified HTTP status code is used.  If the specified status code is not
        one included in httplib.responses, an KeyError exception is raised.

        If this method is not called, the HTTP status will be "200 OK".

        This method must be called before the response is started.  (This really
        only matters for incremental pages that returns the response body in
        chunks; they can't call this method once they've yielded the first body
        chunk.)
        """

        assert not self.__started, "Response already started!"
        if message is None: message = httplib.responses[code]
        self.__status = "%d %s" % (code, message)

    def setContentType(self, content_type):
        """\
        Set the response content type (the "Content-Type" header).

        If the specified content type doesn't have a "charset=X" addition, the
        string "; charset=utf-8" is appended to the content type.

        If this method is not called, the Content-Type header's value will be
        "text/html; charset=utf-8".

        This function must be used rather than addResponseHeader() to set the
        Content-Type header, and must be called before the response is started.
        """

        assert not self.__started, "Response already started!"
        if content_type.startswith("text/") and "charset=" not in content_type: content_type += "; charset=utf-8"
        self.__content_type = content_type

    def addResponseHeader(self, name, value):
        """\
        Add HTTP response header.

        Append a response header to the list of response headers passed to the
        WSGI start_response() callback when the response is started.

        Note: This function does not replace existing headers or merge headers
        with the same name; calling code has to handle such things.  No headers
        (except Content-Type) are added automatically.

        This function must not be used to add a Content-Type header, and must be
        called before the response is started.
        """

        assert not self.__started, "Response already started!"
        assert name.lower() != "content-type", "Use Request.setContentType() instead!"
        self.__response_headers.append((name, value))

    def start(self):
        """\
        Start the response by calling the WSGI start_response() callback.

        This function is called automatically by the main request handling
        function (critic.py::main) and should typically not be called from any
        other code.

        This function can be called multiple times; repeated calls do nothing.
        """

        if not self.__started:
            if self.__status is None:
                self.setStatus(200)
            if self.__content_type is None:
                self.setContentType("text/plain")

            self.__start_response(self.__status, [("Content-Type", self.__content_type)] + self.__response_headers)
            self.__started = True

    def isStarted(self):
        """\
        Check if the response has been started.
        """

        return self.__started

    def getContentType(self):
        """\
        Return the currently set response content type.

        The returned value includes the automatically added "charset=utf-8".  If
        the response hasn't been started yet, and setContentType() hasn't been
        called, None is returned.
        """

        return self.__content_type
