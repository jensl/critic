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
import urllib
import urllib.parse
import http.client
import wsgiref.util

import base
import auth
import configuration
import dbutils

# Paths to which access should be allowed without authentication even if
# anonymous users are not allowed in general.
INSECURE_PATHS = {"login", "validatelogin",
                      "createuser", "registeruser"}

def decodeURIComponent(text):
    """\
    Replace %HH escape sequences and return the resulting string.
    """

    return urllib.parse.unquote_plus(text)

class NoDefault:
    """\
    Placeholder class to signal that a parameter has no default value.

    An instance of this class is provided to Request.getParameter() as the
    'default' argument to signal that it is an error if the parameter is
    not present.
    """

    pass

class HTTPResponse(Exception):
    def __init__(self, status):
        self.status = status
        self.body = []
        self.content_type = "text/plain"

    def execute(self, db, req):
        req.setStatus(self.status)
        if self.body:
            req.setContentType(self.content_type)
        req.start()
        return self.body

class NoContent(HTTPResponse):
    def __init__(self):
        super(NoContent, self).__init__(204)

class NotModified(HTTPResponse):
    def __init__(self):
        super(NotModified, self).__init__(304)

class Forbidden(HTTPResponse):
    def __init__(self, message="Forbidden"):
        super(Forbidden, self).__init__(403)
        self.body = [message]

class NotFound(HTTPResponse):
    def __init__(self, message="Not found"):
        super(NotFound, self).__init__(404)
        self.body = [message]

class Redirect(HTTPResponse):
    def __init__(self, status, location, no_cache=False):
        super(Redirect, self).__init__(status)
        self.location = location
        self.no_cache = no_cache

    def execute(self, db, req):
        from htmlutils import htmlify
        if not req.allowRedirect(self.status):
            self.status = 403
            self.body = ["Cowardly refusing to redirect %s request."
                         % req.method]
        else:
            req.addResponseHeader("Location", self.location)
            self.body = ["<p>Please go here: <a href=%s>%s</a>."
                         % (htmlify(self.location, attributeValue=True),
                            htmlify(self.location))]
            self.content_type = "text/html"
        return super(Redirect, self).execute(db, req)

class Found(Redirect):
    def __init__(self, location):
        super(Found, self).__init__(302, location)

class SeeOther(Redirect):
    def __init__(self, location):
        super(SeeOther, self).__init__(303, location)

class MovedTemporarily(Redirect):
    def __init__(self, location, no_cache=False):
        super(MovedTemporarily, self).__init__(307, location)
        self.no_cache = no_cache

    def execute(self, db, req):
        if self.no_cache:
            req.addResponseHeader("Cache-Control", "no-cache")
        return super(MovedTemporarily, self).execute(db, req)

class NeedLogin(MovedTemporarily):
    def __init__(self, source, optional=False):
        if isinstance(source, Request):
            target = source.getTargetURL()
        else:
            target = str(source)
        location = "/login?target=%s" % urllib.parse.quote(target)
        if optional:
            location += "&optional=yes"
        return super(NeedLogin, self).__init__(location, no_cache=True)

class RequestHTTPAuthentication(HTTPResponse):
    def __init__(self):
        super(RequestHTTPAuthentication, self).__init__(401)

    def execute(self, db, req):
        import page.utils

        self.body = str(page.utils.displayMessage(
            db, req, dbutils.User.makeAnonymous(),
            title="Authentication required",
            message=("You must provide valid HTTP authentication to access "
                     "this system.")))
        self.content_type = "text/html"

        req.addResponseHeader("WWW-Authenticate", "Basic realm=\"Critic\"")
        return super(RequestHTTPAuthentication, self).execute(db, req)

class DisplayMessage(base.Error):
    """\
    Utility exception raised by pages to display a simply message.
    """

    def __init__(self, title, body=None, review=None, html=False, status=200):
        self.title = title
        self.body = body
        self.review = review
        self.html = html
        self.status = status

class InvalidParameterValue(DisplayMessage):
    """\
    Exception raised by pages when a query parameter has an invalid value.

    This exception is automatically raised by Request.getParameter() if the
    parameter's value can't be converted as requested.
    """

    def __init__(self, name, value, expected):
        DisplayMessage.__init__(self, "Invalid URI Parameter Value!", "Got '%s=%s', expected %s." % (name, value, expected), status=400)

class MissingParameter(DisplayMessage):
    """\
    Exception raised by pages when a required query parameter is missing.

    This exception is automatically raised by Request.getParameter() if the
    parameter is required and missing.
    """

    def __init__(self, name):
        DisplayMessage.__init__(self, "Missing URI Parameter!", "Expected '%s' parameter." % name, status=400)

class MissingWSGIRemoteUser(Exception):
    """\
    Exception raised if WSGI environ "REMOTE_USER" is missing.

    This error happens when Critic is running in "host" authentication mode but no
    REMOTE_USER variable was present in the WSGI environ dict provided by the
    web server.
    """
    pass

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
    original_query == same as 'query', unless the path is a short-hand for
                      another path, in which case 'query' is typically extended
                      with parameters derived from the short-hand path

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

        self.__db = db
        self.__environ = environ
        self.__start_response = start_response
        self.__status = None
        self.__content_type = None
        self.__response_headers = []
        self.__started = False

        content_length = environ.get("CONTENT_LENGTH")
        self.__request_body_length = int(content_length) if content_length else 0
        self.__request_body_read = 0

        self.server_name = \
            self.getRequestHeader("X-Forwarded-Host") \
            or environ.get("SERVER_NAME") \
            or configuration.base.HOSTNAME

        self.method = environ.get("REQUEST_METHOD", "")
        self.path = environ.get("PATH_INFO", "").lstrip("/")
        self.original_path = self.path
        self.query = environ.get("QUERY_STRING", "")
        self.parsed_query = urllib.parse.parse_qs(self.query, keep_blank_values=True)
        self.original_query = self.query
        self.cookies = {}

        header = self.getRequestHeader("Cookie")
        if header:
            for cookie in map(str.strip, header.split(";")):
                name, _, value = cookie.partition("=")
                if name and value:
                    self.cookies[name] = value

        self.session_type = configuration.base.SESSION_TYPE

    def updateQuery(self, items):
        self.parsed_query.update(items)
        self.query = urllib.parse.urlencode(
            sorted(self.parsed_query.items()), doseq=True)

    @property
    def user(self):
        return self.__db.user

    def getTargetURL(self):
        target = "/" + self.path
        if self.query:
            target += "?" + self.query
        return target

    def getRequestURI(self):
        return wsgiref.util.request_uri(self.__environ)

    def getEnvironment(self):
        return self.__environ

    def getParameter(self, name, default=NoDefault, filter=lambda value: value):
        """\
        Get URI query parameter.

        If the requested parameter was not present in the URI query component,
        the supplied default value is returned instead, or, if the supplied
        default value is the NoDefault class, a MissingParameter exception is
        raised.

        If a filter function is supplied, it is called with a single argument,
        the string value of the URI parameter, and its return value is returned
        from getParameter().  If the filter function raises an exception (other
        than DisplayMessage or sub-classes thereof) an InvalidParameterValue
        exception is raised.  Note: the filter function is not applied to
        default values, meaning that the default value can be of a different
        type than actual parameter values.
        """

        value = self.parsed_query.get(name)

        if value is None:
            if default is NoDefault:
                raise MissingParameter(name)
            return default

        def filter_value(value):
            try:
                return filter(value)
            except (base.Error, auth.AccessDenied):
                raise
            except Exception:
                if filter is int:
                    expected = "integer"
                else:
                    expected = "something else"
                raise InvalidParameterValue(name, value, expected)

        value = [filter_value(element) for element in value]

        if len(value) == 1:
            return value[0]

        return value

    def getParameters(self):
        return { name: value[0] if len(value) == 1 else value
                 for name, value in self.parsed_query.items() }

    def getRequestHeader(self, name, default=None):
        """\
        Get HTTP request header by name.

        The name is case-insensitive.  If the request header was not present in
        the request, the default value is returned (or None if no default value
        is provided.)  If the request header was present, its value is returned
        as a string.
        """

        return self.__environ.get("HTTP_" + name.upper().replace("-", "_"), default)

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

    def read(self, bufsize=None):
        """\
        Return the HTTP request body, or an empty string if there is none.
        """

        if self.__request_body_length:
            max_bufsize = self.__request_body_length - self.__request_body_read

            if bufsize is None:
                bufsize = max_bufsize
            else:
                bufsize = min(bufsize, max_bufsize)

        if "wsgi.input" not in self.__environ or not bufsize:
            return ""

        data = self.__environ["wsgi.input"].read(bufsize)
        self.__request_body_read += len(data)
        return data

    def write(self, data):
        """
        Write HTTP response body chunk.
        """

        self.__write(data)

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
        if message is None: message = http.client.responses[code]
        self.__status = "%d %s" % (code, message)

    def hasContentType(self):
        return self.__content_type is not None

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

    def setCookie(self, name, value, secure=False):
        if secure and configuration.base.ACCESS_SCHEME != "http":
            modifier = "Secure"
        else:
            modifier = "HttpOnly"
        self.addResponseHeader(
            "Set-Cookie",
            "%s=%s; Max-Age=31536000; Path=/; %s" % (name, value, modifier))

    def deleteCookie(self, name):
        if name in self.cookies:
            self.addResponseHeader(
                "Set-Cookie",
                "%s=invalid; Path=/; Expires=Thursday 01-Jan-1970 00:00:00 GMT" % name)

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

            headers = [("Content-Type", self.__content_type)]
            headers.extend(self.__response_headers)

            self.__write = self.__start_response(self.__status, headers)
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

    def ensureSecure(self):
        if configuration.base.ACCESS_SCHEME != "http":
            current_url = self.getRequestURI()
            secure_url = re.sub("^http:", "https:", current_url)

            if current_url != secure_url:
                raise MovedTemporarily(secure_url, True)

    def requestHTTPAuthentication(self, realm="Critic"):
        self.setStatus(401)
        self.addResponseHeader("WWW-Authenticate", "Basic realm=\"%s\"" % realm)
        self.start()

    def allowRedirect(self, status):
        """Return true if it is safe to redirect this request"""
        return self.method in ("GET", "HEAD") or status == 303
