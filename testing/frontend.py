# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

import json
import contextlib
import urllib

try:
    import requests
    import BeautifulSoup
except ImportError:
    # testing/main.py detects and abort if either of these are missing, so just
    # ignore errors here.
    pass

import testing

class Error(testing.TestFailure):
    def __init__(self, url, message):
        super(Error, self).__init__("page '%s' failed: %s" % (url, message))
        self.url = url

class HTTPError(Error):
    def __init__(self, url, expected, actual, body=None):
        message = "HTTP status differs: expected=%r, actual=%r" % (expected, actual)
        if body:
            message += "\n" + body
        super(HTTPError, self).__init__(url, message)
        self.expected = expected
        self.actual = actual

class PageError(Error):
    def __init__(self, url, key, expected, actual):
        super(PageError, self).__init__(
            url, "%s differs: expected=%r, actual=%r" % (key, expected, actual))
        self.key = key
        self.expected = expected
        self.actual = actual

class OperationError(Error):
    def __init__(self, url, message=None, key=None, expected=None, actual=None):
        if message is None:
            message = ""
        if key:
            message += "%s differs: expected=%r, actual=%r" % (key, expected, actual)
        super(OperationError, self).__init__(url, message)
        self.key = key
        self.expected = expected
        self.actual = actual

class NoSession(object):
    def apply(self, kwargs):
        pass

class CookieSession(object):
    def __init__(self, sid=None):
        self.sid = sid

    def apply(self, kwargs):
        headers = kwargs.setdefault("headers", {})
        headers["Cookie"] = "sid=%s; has_sid=1" % self.sid

class HTTPAuthSession(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def apply(self, kwargs):
        kwargs["auth"] = (self.username, self.password)

class Frontend(object):
    def __init__(self, hostname, http_port=8080):
        self.hostname = hostname
        self.http_port = http_port
        self.sessions = [NoSession()]
        self.pending_session = None
        self.instance = None

    def prefix(self, username=None):
        if username:
            username += "@"
        else:
            username = ""
        return "http://%s%s:%d" % (username, self.hostname, self.http_port)

    def page(self, url, params={}, expect={},
             expected_content_type="text/html",
             expected_http_status=200,
             disable_redirects=False):
        full_url = "%s/%s" % (self.prefix(), url)

        log_url = full_url
        if params:
            query = urllib.urlencode(sorted(params.items()))
            log_url = "%s?%s" % (log_url, query)

        testing.logger.debug("Fetching page: %s ..." % log_url)

        kwargs = {}

        self.sessions[-1].apply(kwargs)

        response = requests.get(full_url,
                                params=params,
                                allow_redirects=not disable_redirects,
                                **kwargs)

        if "sid" in response.cookies:
            testing.logger.debug("Cookie: sid=%s" % response.cookies["sid"])
            if self.pending_session:
                self.pending_session.sid = response.cookies["sid"]

        def text(response):
            if hasattr(response, "text"):
                if callable(response.text):
                    return response.text()
                else:
                    return response.text
            else:
                return response.content

        if isinstance(expected_http_status, int):
            expected_http_status = [expected_http_status]

        try:
            if response.status_code not in expected_http_status:
                if response.headers["content-type"].startswith("text/plain"):
                    body = text(response)
                else:
                    body = None
                raise HTTPError(url, expected_http_status, response.status_code, body)
        except testing.TestFailure as error:
            testing.logger.error("Page '%s': %s" % (url, error.message))
            raise testing.TestFailure

        if response.status_code >= 400 and 200 in expected_http_status:
            # The caller expected a successful load or an error.  Signal errors
            # by returning None.
            return None

        if response.status_code >= 300 and response.status_code < 400 \
                and disable_redirects:
            # Redirection, and the caller disabled following it.  The caller is
            # interested in the redirect itself, so return the whole response.
            return response

        testing.logger.debug("Fetched page: %s" % log_url)

        document = text(response)

        content_type, _, _ = response.headers["content-type"].partition(";")

        if isinstance(expected_content_type, str):
            expected_content_type = (expected_content_type,)

        if response.status_code == 200:
            if content_type not in expected_content_type:
                testing.logger.error(
                    "Page '%s': wrong content type: %s" % (url, content_type))
                raise testing.TestFailure

        if content_type == "text/html":
            document = BeautifulSoup.BeautifulSoup(document)

            div_fatal = document.find("div", attrs={ "class": "fatal" })
            if div_fatal:
                message = div_fatal.find("pre")
                testing.logger.error(
                    "Page '%s': crash during incremental page generation:\n%s"
                    % (url, message.string if message else "<no message found>"))
                raise testing.TestFailure

        if expect:
            testing.logger.debug("Checking page: %s ..." % log_url)

            failed_checks = False

            for key, check in expect.items():
                try:
                    check(document)
                except testing.expect.FailedCheck as failed_check:
                    testing.logger.error("Page '%s', test '%s': %s"
                                         % (url, key, failed_check.message))
                    failed_checks = True
                except Exception as error:
                    raise Error(url, "'%s' checker failed: %s" % (key, str(error)))

            if failed_checks:
                raise testing.TestFailure

            testing.logger.debug("Checked page: %s ..." % log_url)

        return document

    def operation(self, url, data, expect={}):
        full_url = "%s/%s" % (self.prefix(), url)

        testing.logger.debug("Executing operation: %s ..." % full_url)

        kwargs = {}

        self.sessions[-1].apply(kwargs)

        if not isinstance(data, basestring):
            data = json.dumps(data)
            kwargs.setdefault("headers", {})["Content-Type"] = "text/json"

        response = requests.post(full_url,
                                 data=data,
                                 **kwargs)

        try:
            if response.status_code != 200:
                raise HTTPError(url, 200, response.status_code)

            if expect is None:
                result = response.content
            elif hasattr(response, "json"):
                if callable(response.json):
                    try:
                        result = response.json()
                    except:
                        raise OperationError(url, message="malformed response (not JSON)")
                else:
                    result = response.json
                    if result is None:
                        raise OperationError(url, message="malformed response (not JSON)")
            else:
                try:
                    result = json.loads(response.content)
                except ValueError:
                    raise OperationError(url, message="malformed response (not JSON)")
        except testing.TestFailure as error:
            testing.logger.error("Operation '%s': %s" % (url, error.message))
            raise testing.TestFailure

        if "sid" in response.cookies:
            testing.logger.debug("Cookie: sid=%s" % response.cookies["sid"])
            if self.pending_session:
                self.pending_session.sid = response.cookies["sid"]

        testing.logger.debug("Executed operation: %s" % full_url)

        if expect is not None:
            testing.logger.debug("Checking operation: %s" % full_url)

            # Check result["status"] first; if it doesn't have the expected value,
            # it's likely all other expected keys are simply missing from the
            # result, and thus produce rather meaningless errors.
            expected = expect.get("status", "ok")
            actual = result.get("status")
            if actual != expected:
                if actual == "error":
                    extra = "\nError:\n  %s" % "\n  ".join(result.get("error").splitlines())
                elif actual == "failure":
                    extra = " (code=%r)" % result.get("code")
                else:
                    extra = ""
                testing.logger.error(
                    "Operation '%s', key 'status': check failed: "
                    "expected=%r, actual=%r%s"
                    % (url, expected, actual, extra))
                raise testing.TestFailure

            failed_checks = False

            # Then check any other expected keys.
            for key, expected in expect.items():
                if key != "status":
                    actual = result.get(key)
                    if callable(expected):
                        checked = expected(actual)
                        if checked:
                            expected, actual = checked
                        else:
                            continue
                    if expected != actual:
                        testing.logger.error(
                            "Operation '%s', key '%s': check failed: "
                            "expected=%r, actual=%r"
                            % (url, key, expected, actual))
                        failed_checks = True

            if failed_checks:
                raise testing.TestFailure

            testing.logger.debug("Checked operation: %s" % full_url)

        return result

    def json(self, path, expect=None, params={}, expected_http_status=200,
             post=None, put=None, delete=False):
        url = "api/v1/" + path
        full_url = "http://%s:%d/%s" % (self.hostname, self.http_port, url)

        log_url = full_url
        if params:
            query = urllib.urlencode(sorted(params.items()))
            log_url = "%s?%s" % (log_url, query)

        kwargs = { "params": params,
                   "headers": { "Accept": "application/vnd.api+json" } }
        method = "GET"

        self.sessions[-1].apply(kwargs)

        if post:
            method = "POST"
            kwargs["data"] = json.dumps(post)
        elif put:
            method = "PUT"
            kwargs["data"] = json.dumps(put)
        elif delete:
            method = "DELETE"

        testing.logger.debug("Accessing JSON API: %s %s ..."
                             % (method, log_url))

        response = requests.request(method, full_url, **kwargs)

        testing.logger.debug("Accessed JSON API: %s %s ..."
                             % (method, log_url))

        try:
            if response.status_code != expected_http_status:
                raise HTTPError(url, expected_http_status, response.status_code)

            if response.status_code == 204:
                # No content.
                return None

            if hasattr(response, "json"):
                if callable(response.json):
                    try:
                        result = response.json()
                    except:
                        raise OperationError(url, message="malformed response (not JSON)")
                else:
                    result = response.json
                    if result is None:
                        raise OperationError(url, message="malformed response (not JSON)")
            else:
                try:
                    result = json.loads(response.content)
                except ValueError:
                    raise OperationError(url, message="malformed response (not JSON)")
        except testing.TestFailure as error:
            testing.logger.error("JSON '%s': %s" % (path, error.message))
            raise testing.TestFailure

        def deunicode(value):
            if isinstance(value, list):
                return [deunicode(v) for v in value]
            elif isinstance(value, dict):
                return { deunicode(k): deunicode(v) for k, v in value.items() }
            elif isinstance(value, unicode):
                return value.encode("utf-8")
            return value

        result = deunicode(result)

        if expect is None:
            return result

        testing.logger.debug("Checking JSON: %s" % log_url)

        errors = []

        def describe(value):
            if isinstance(value, dict) or value is dict:
                return "object"
            if isinstance(value, list) or value is list:
                return "array"
            if isinstance(value, type):
                return { int: "integer", float: "float", str: "string" }[value]
            if isinstance(value, (str, int, float)):
                return repr(value)
            if value is None:
                return "null"
            return "unexpected"

        def check_object(path, expected, actual):
            if not isinstance(actual, dict):
                errors.append("%s: value is %s, expected object"
                              % (path, describe(actual)))
                return
            if expected is dict:
                return
            expected_keys = set(expected.keys())
            actual_keys = set(actual.keys())
            if expected_keys - actual_keys:
                errors.append("%s: missing keys: %r"
                              % (path, tuple(expected_keys - actual_keys)))
            if actual_keys - expected_keys:
                errors.append("%s: unexpected keys: %r"
                              % (path, tuple(actual_keys - expected_keys)))
            for key in sorted(expected_keys & actual_keys):
                check("%s/%s" % (path, key), expected[key], actual[key])

        def check_array(path, expected, actual):
            if not isinstance(actual, list):
                errors.append("%s: value is %s, expected array"
                            % (path, describe(actual)))
            if expected is list:
                return
            if len(actual) != len(expected):
                errors.append("%s: wrong array length: got %s, expected %s"
                              % (path, len(actual), len(expected)))
                return
            for index, (expected, actual) in enumerate(zip(expected, actual)):
                check("%s[%d]" % (path, index), expected, actual)

        def check_null(path, actual):
            if actual is not None:
                errors.append("%s: value is %s, expected null"
                              % (path, describe(actual)))

        def check_value(path, expected, actual):
            if isinstance(actual, (dict, list)):
                errors.append("%s: value is %s, expected %s"
                              % (path, describe(actual), describe(expected)))
            if isinstance(expected, type):
                if not isinstance(actual, expected):
                    errors.append("%s: wrong value: got %r, expected %r"
                                  % (path, actual, describe(expected)))
            elif actual != expected:
                errors.append("%s: wrong value: got %r, expected %r"
                              % (path, actual, expected))

        def check(path, expected, actual):
            errors_before = len(errors)
            if callable(expected) and not isinstance(expected, type):
                errors.extend(expected(path, actual, check) or ())
            elif isinstance(expected, dict) or expected is dict:
                check_object(path, expected, actual)
            elif isinstance(expected, list) or expected is list:
                check_array(path, expected, actual)
            elif expected is None:
                check_null(path, actual)
            else:
                check_value(path, expected, actual)
            return errors_before == len(errors)

        check(path, expect, result)

        if errors:
            testing.logger.error("Wrong JSON received for %s:\n  %s"
                                 % (path, "\n  ".join(errors)))
            testing.logger.error("Received JSON: %r" % result)

        testing.logger.debug("Checked JSON: %s" % log_url)

        return result

    @contextlib.contextmanager
    def cookie_session(self, operation):
        if not self.pending_session.sid:
            testing.expect.check("<signed in after %s>" % operation,
                                 "<no session cookie received>")
        testing.logger.debug("Starting cookie session")
        self.sessions.append(self.pending_session)
        self.pending_session = None
        try:
            yield
        finally:
            try:
                self.operation("endsession", data={})
            except testing.TestFailure as failure:
                if failure.message:
                    testing.logger.error(failure.message)
            except Exception:
                testing.logger.exception("Failed to sign out!")

            # Dropping the cookie effectively signs out even if the "endsession"
            # operation failed.
            self.sessions.pop()

            testing.logger.debug("Ended cookie session")

    @contextlib.contextmanager
    def no_session(self):
        self.sessions.append(NoSession())
        try:
            yield
        finally:
            self.sessions.pop()

    def collect_session_cookie(self):
        self.pending_session = CookieSession()

    def validatelogin(self, username, password, expect_failure=False):
        data = { "fields": { "username": username,
                             "password": password }}

        # Check if the current commit predates the user authentication
        # restructuring that added the "fields" wrapper.
        if self.instance.current_commit:
            if not testing.exists_at(
                    self.instance.current_commit, "src/auth/database.py"):
                data = data["fields"]

        if expect_failure:
            expect = { "message": expect_failure }
        else:
            expect = { "message": None }

        self.operation(
            "validatelogin",
            data=data,
            expect=expect)

    @contextlib.contextmanager
    def signin(self, username="admin", password="testing", use_httpauth=False,
               access_token=None):
        if access_token:
            username = access_token["part1"]
            password = access_token["part2"]
            use_httpauth = True
        if use_httpauth:
            self.sessions.append(HTTPAuthSession(username, password))
            try:
                yield
            finally:
                self.sessions.pop()
        else:
            with self.no_session():
                self.collect_session_cookie()
                self.validatelogin(username, password)
                with self.cookie_session("/validatelogin"):
                    yield

    def run_basic_tests(self):
        # The /tutorials page is essentially static content and doesn't require
        # a signed in user, so a good test-case for checking if the site is up
        # and accessible at all.
        self.page("tutorial", expect={ "document_title": testing.expect.document_title(u"Tutorials"),
                                       "content_title": testing.expect.paleyellow_title(0, u"Tutorials") })

        # The /validatelogin operation is a) necessary for most meaningful
        # additional testing, and b) a simple enough operation to test.
        with self.signin():
            # Load /home to determine whether /validatelogin successfully signed in
            # (and that we stored the session id cookie correctly.)
            self.page("home", expect={ "document_title": testing.expect.document_title(u"Testing Administrator's Home"),
                                       "content_title": testing.expect.paleyellow_title(0, u"Testing Administrator's Home") })
