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

import aiohttp.web
import functools
import http.client
import logging
import queue
import re
import threading

logger = logging.getLogger(__name__)

from critic import base
from critic import api
from critic import auth

# Paths to which access should be allowed without authentication even if
# anonymous users are not allowed in general.
INSECURE_PATHS = {"login", "validatelogin", "createuser", "registeruser"}


def decodeURIComponent(text):
    """\
    Replace %HH escape sequences and return the resulting string.
    """

    import urllib.parse

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

    async def execute(self, req):
        req.setStatus(self.status)
        if self.body:
            req.setContentType(self.content_type)
        await req.start()
        return [part.encode() for part in self.body]


class NoContent(HTTPResponse):
    def __init__(self):
        super().__init__(204)


class NotModified(HTTPResponse):
    def __init__(self):
        super().__init__(304)


class BadRequest(HTTPResponse):
    def __init__(self, message="Bad Request"):
        super().__init__(400)
        self.body = [message]


class Forbidden(HTTPResponse):
    def __init__(self, message="Forbidden"):
        super().__init__(403)
        self.body = [message]


class NotFound(HTTPResponse):
    def __init__(self, message="Not found"):
        super().__init__(404)
        self.body = [message]


class Redirect(HTTPResponse):
    def __init__(self, status, location, no_cache=False):
        super().__init__(status)
        self.location = location
        self.no_cache = no_cache

    async def execute(self, req):
        from ..htmlutils import htmlify

        if not req.allowRedirect(self.status):
            self.status = 403
            self.body = ["Cowardly refusing to redirect %s request." % req.method]
        else:
            req.addResponseHeader("Location", self.location)
            self.body = [
                "<p>Please go here: <a href=%s>%s</a>."
                % (htmlify(self.location, attributeValue=True), htmlify(self.location))
            ]
            self.content_type = "text/html"
        return await super().execute(req)


class Found(Redirect):
    def __init__(self, location):
        super().__init__(302, location)


class SeeOther(Redirect):
    def __init__(self, location):
        super().__init__(303, location)


class MovedTemporarily(Redirect):
    def __init__(self, location, no_cache=False):
        super().__init__(307, location)
        self.no_cache = no_cache

    async def execute(self, req):
        if self.no_cache:
            req.addResponseHeader("Cache-Control", "no-cache")
        return await super().execute(req)


class NeedLogin(MovedTemporarily):
    def __init__(self, source, optional=False):
        import urllib.parse

        if isinstance(source, Request):
            target = source.getTargetURL()
        else:
            target = str(source)
        location = "/login?target=%s" % urllib.parse.quote(target)
        if optional:
            location += "&optional=yes"
        return super().__init__(location, no_cache=True)


class RequestHTTPAuthentication(HTTPResponse):
    def __init__(self):
        super().__init__(401)

    async def execute(self, req):
        self.body = "Authentication required"
        self.content_type = "text/plain"

        req.addResponseHeader("WWW-Authenticate", 'Basic realm="Critic"')
        return await super().execute(req)


class InternalServerError(HTTPResponse):
    def __init__(self, message="Internal Server Error"):
        super().__init__(500)
        self.body = [message]


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
        DisplayMessage.__init__(
            self,
            "Invalid URI Parameter Value!",
            "Got '%s=%s', expected %s." % (name, value, expected),
            status=400,
        )


class MissingParameter(Exception):
    """\
    Exception raised by pages when a required query parameter is missing.

    This exception is automatically raised by Request.getParameter() if the
    parameter is required and missing.
    """

    def __init__(self, name):
        super().__init__(f"Missing required query parameter: {name!r}")
        self.name = name


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

    def __init__(self, critic):
        """\
        Construct request wrapper.

        The environ and start_response arguments should be the arguments to the
        WSGI application object.
        """

        self.__critic = critic
        self.__status = None
        self.__content_type = None
        self.__content_encoding = None
        self.__response_headers = []
        self.__started = False

        self.cookies = {}

        header = self.getRequestHeader("Cookie")
        if header:
            for cookie in map(str.strip, header.split(";")):
                name, _, value = cookie.partition("=")
                if name and value:
                    self.cookies[name] = value

        self.session_type = api.critic.settings().frontend.session_type

    def setMethod(self, method):
        self.method = method or "GET"

    def setPath(self, path):
        self.original_path = self.path = (path or "").lstrip("/")

    def setQuery(self, query):
        import urllib.parse

        self.original_query = self.query = query or ""
        self.parsed_query = urllib.parse.parse_qs(self.query, keep_blank_values=True)

    def updateQuery(self, items):
        import urllib.parse

        self.parsed_query.update(items)
        self.query = urllib.parse.urlencode(
            sorted(self.parsed_query.items()), doseq=True
        )

    @property
    def critic(self):
        return self.__critic

    @property
    def user(self):
        return self.__critic.database.user

    def getTargetURL(self):
        target = "/" + self.path
        if self.query:
            target += "?" + self.query
        return target

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
        return {
            name: value[0] if len(value) == 1 else value
            for name, value in self.parsed_query.items()
        }

    def getReferrer(self):
        try:
            return self.getRequestHeader("Referer")
        except:
            return "N/A"

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
        if message is None:
            message = http.client.responses[code]
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
        if content_type:
            if content_type.startswith("text/") and "charset=" not in content_type:
                content_type += "; charset=utf-8"
            self.__content_type = content_type

    def setContentEncoding(self, content_encoding):
        assert not self.__started, "Response already started!"
        self.__content_encoding = content_encoding

    def cacheForever(self):
        self.__response_headers.extend(
            [
                ("Last-Modified", "Thu, 01 Jan 1970 00:00:00 GMT"),
                ("Expires", "Tue, 01 Feb 2050 00:00:00 GMT"),
                ("Cache-Control", "max-age=%d" % (60 * 60 * 24 * 365 * 20)),
            ]
        )

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
        if secure and api.critic.settings().frontend.access_scheme != "http":
            modifier = "Secure"
        else:
            modifier = "HttpOnly"
        self.addResponseHeader(
            "Set-Cookie",
            "%s=%s; Max-Age=31536000; Path=/; %s" % (name, value, modifier),
        )

    def deleteCookie(self, name):
        if name in self.cookies:
            self.addResponseHeader(
                "Set-Cookie",
                "%s=invalid; Path=/; Expires=Thursday 01-Jan-1970 00:00:00 GMT" % name,
            )

    def getRequestHeader(self, name, default=None):
        return default

    async def start(self):
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
            if self.__content_encoding:
                headers.append(("Content-Encoding", self.__content_encoding))
            headers.extend(self.__response_headers)

            self.__started = True

            return await self.startResponse(self.__status, headers)

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
        if api.critic.settings().frontend.access_scheme != "http":
            current_url = self.getRequestURI()
            secure_url = re.sub("^http:", "https:", current_url)

            if current_url != secure_url:
                raise MovedTemporarily(secure_url, True)

    def requestHTTPAuthentication(self, realm="Critic"):
        self.setStatus(401)
        self.addResponseHeader("WWW-Authenticate", 'Basic realm="%s"' % realm)
        self.start()

    def allowRedirect(self, status):
        """Return true if it is safe to redirect this request"""
        return self.method in ("GET", "HEAD") or status == 303

    @staticmethod
    def make(critic, method, path, **params):
        import urllib.parse

        request = Request(critic)
        request.setMethod(method)
        request.setPath(path)
        if params:
            request.setQuery(urllib.parse.urlencode(params))
        return request


class WSGIRequest(Request):
    def __init__(self, critic, environ, start_response):
        self.__environ = environ
        self.__start_response = start_response

        super().__init__(critic)

        self.setMethod(environ.get("REQUEST_METHOD"))
        self.setPath(environ.get("PATH_INFO"))
        self.setQuery(environ.get("QUERY_STRING"))

        self.__read_queue = self.__read_thread = None
        self.__request_body_length = int(environ.get("CONTENT_LENGTH") or 0)
        self.__request_body_read = 0

    def getRequestHeader(self, name, default=None):
        """\
        Get HTTP request header by name.

        The name is case-insensitive.  If the request header was not present in
        the request, the default value is returned (or None if no default value
        is provided.)  If the request header was present, its value is returned
        as a string.
        """

        cgi_name = "HTTP_" + name.upper().replace("-", "_")
        return self.__environ.get(cgi_name, default)

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

    def getRequestURI(self):
        import wsgiref.util

        return wsgiref.util.request_uri(self.__environ)

    def getEnvironment(self):
        return self.__environ

    async def startResponse(self, status, headers):
        self.__write = self.__start_response(status, headers)

    async def read(self, bufsize=None):
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

        def read_input(stream, queue):
            while True:
                item = queue.get()
                if item is None:
                    break
                callback, bufsize = item
                callback(stream.read(bufsize))

        if not self.__read_queue:
            self.__read_queue = queue.Queue()
            self.__read_thread = threading.Thread(
                target=read_input,
                args=(self.__environ["wsgi.input"], self.__read_queue),
            )
            self.__read_thread.daemon = True
            self.__read_thread.start()

        loop = self.critic.loop
        future = loop.create_future()

        self.__read_queue.put(
            (functools.partial(loop.call_soon_threadsafe, future.set_result), bufsize)
        )

        data = await future
        self.__request_body_read += len(data)
        return data

    def write(self, data):
        """
        Write HTTP response body chunk.
        """

        self.__write(data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.__read_queue:
            self.__read_queue.put(None)
            self.__read_thread.join()


class AIOHTTPRequest(Request):
    def __init__(self, critic: api.critic.Critic, request: aiohttp.web.BaseRequest):
        self.__request = request
        self.__response = None
        self.__mode = None

        super().__init__(critic)

        self.setMethod(request.method)
        self.setPath(request.path)
        self.setQuery(request.query_string)

        self.finished = False

    @property
    def response(self):
        return self.__response

    def getRequestHeader(self, name, default=None):
        return self.__request.headers.get(name, default)

    def getRequestHeaders(self):
        return self.__request.headers

    def getRequestURI(self):
        return str(self.__request.url)

    def getEnvironment(self):
        environ = {"REMOTE_ADDR": self.__request.remote}
        if "Content-Type" in self.__request.headers:
            environ["CONTENT_TYPE"] = self.__request.headers["Content-Type"]
        for name, value in self.__request.headers.items():
            environ["HTTP_" + name.upper().replace("-", "_")] = value
        return environ

    async def startResponse(self, status, headers):
        import aiohttp.web

        code, _, reason = status.partition(" ")
        code = int(code)

        self.__response = aiohttp.web.StreamResponse(status=code, reason=reason)
        self.__mode = "stream"

        for key, value in headers:
            self.__response.headers.add(key, value)

        return await self.__response.prepare(self.__request)

    async def startWebSocketResponse(self, *, protocols=()):
        import aiohttp.web

        self.__response = aiohttp.web.WebSocketResponse(protocols=protocols)
        self.__mode = "websocket"

        ws_ready = self.__response.can_prepare(self.__request)
        if not ws_ready:
            raise aiohttp.web.HTTPBadRequest()

        await self.__response.prepare(self.__request)
        return ws_ready.protocol

    async def closeWebSocketResponse(self, *, code=1000, message=""):
        assert self.__mode == "websocket"
        await self.__response.close(code=code, message=message)

    async def sendWebSocketMessage(self, data):
        logger.debug("sendWebSocketMessage: %r", data)
        await self.__response.send_str(data)

    async def read(self, bufsize=None):
        return await self.__request.content.read(bufsize or -1)

    async def write(self, data):
        assert self.__response is not None
        await self.__response.write(data)

    async def write_eof(self):
        assert self.__response is not None
        await self.__response.write_eof()
        self.finished = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.__response:
            await self.write_eof()

    def __aiter__(self):
        assert self.__mode == "websocket"
        return self.__response.__aiter__()
