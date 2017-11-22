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

import contextlib
import json
import re
import requests
import traceback
import urllib

import testing


class Error(testing.TestFailure):
    def __init__(self, method, path, message):
        super().__init__(f"request '{method} {path}' failed: {message}")
        self.path = path


class HTTPError(Error):
    def __init__(self, method, path, expected, actual, body=None):
        message = f"HTTP status differs: expected={expected}, actual={actual}"
        if body:
            message += "\n" + body
        super(HTTPError, self).__init__(method, path, message)
        self.expected = expected
        self.actual = actual


class AccessDenied(Error):
    def __init__(self, method, path, message):
        super().__init__(method, path, message)
        self.message = message


class SessionBase(object):
    def apply(self, kwargs):
        pass

    def process_response(self, response):
        if "sid" in response.cookies:
            raise Error(
                response.request.method, response.url, "unexpected session cookie set"
            )


class NoSession(SessionBase):
    pass


class CookieSession(SessionBase):
    def __init__(self, sid=None):
        self.sid = sid

    def __repr__(self):
        return "CookieSession(sid=%r)" % self.sid

    def apply(self, kwargs):
        if self.sid is not None:
            headers = kwargs.setdefault("headers", {})
            headers["Cookie"] = "sid=%s; has_sid=1" % self.sid

    def process_response(self, response):
        for name, value in response.cookies.items():
            if name == "sid":
                self.sid = value
            elif name == "has_sid" and value == "0":
                # This means we've signed out. The response would also have
                # deleted the "sid" cookie, but unfortunately we can't really
                # get that information from the response.
                self.sid = None


class HTTPAuthSession(SessionBase):
    def __init__(self, *, username=None, password=None, token=None):
        self.username = username
        self.password = password
        self.token = token

    def apply(self, kwargs):
        if self.username:
            kwargs["auth"] = (self.username, self.password or self.token)
        elif self.token:
            headers = kwargs.setdefault("headers", {})
            headers["authorization"] = f"Bearer {self.token}"


class Frontend(object):
    def __init__(self, hostname, http_port=8080):
        self.hostname = hostname
        self.http_port = http_port
        self.instance = None

    def reset_for_test(self):
        self.sessions = [NoSession()]
        self.session_cookies = {}

    @property
    def current_session(self):
        return self.sessions[-1]

    def prefix(self, username=None):
        if username:
            username += "@"
        else:
            username = ""
        if self.http_port != 80:
            port = f":{self.http_port}"
        else:
            port = ""
        return "http://%s%s%s" % (username, self.hostname, port)

    def request(
        self, path, *, params=None, post=None, put=None, delete=False, **kwargs
    ):
        params = dict(params or {})

        self.current_session.apply(kwargs)

        if post is not None:
            method = "POST"
            kwargs["data"] = json.dumps(post)
        elif put is not None:
            method = "PUT"
            kwargs["data"] = json.dumps(put)
        elif delete:
            method = "DELETE"
        else:
            method = "GET"

        # No built-in HTTP endpoints returns a redirect, except the OAuth API, which
        # redirects to external (fake) servers, and for which we want to check the
        # redirect rather than load the target URL.
        kwargs.setdefault("allow_redirects", False)

        testing.logger.debug(f"{kwargs=}")

        response = requests.request(
            method,
            f"http://{self.hostname}:{self.http_port}/{path}",
            params=params,
            **kwargs,
        )

        self.current_session.process_response(response)

        return response

    def json(
        self,
        path,
        *,
        expect=None,
        extract=None,
        check=None,
        params=None,
        include=None,
        expected_http_status=None,
        post=None,
        put=None,
        delete=False,
        expect_access_denied=None,
        **kwargs,
    ):
        full_path = "api/v1/" + path

        log_url = f"http://{self.hostname}:{self.http_port}/{full_path}"
        if params:
            query = urllib.parse.urlencode(sorted(params.items()))
            log_url = "%s?%s" % (log_url, query)

        if post is not None:
            method = "POST"
            payload = post
        elif put is not None:
            method = "PUT"
            payload = put
        else:
            payload = None
            if delete:
                method = "DELETE"
            else:
                method = "GET"

        if expected_http_status is None:
            expected_http_status = 200 if not delete else 204

        testing.logger.debug("Accessing JSON API: %s %s ..." % (method, log_url))

        if payload is not None:
            kwargs["data"] = json.dumps(payload)
            testing.logger.debug("Payload: %s", json.dumps(payload, indent=2))

        if include is not None:
            params["include"] = ",".join(include)

        response = self.request(
            full_path,
            params=params,
            post=post,
            put=put,
            delete=delete,
            headers={"Accept": "application/vnd.api+json"},
            **kwargs,
        )

        testing.logger.debug("Accessed JSON API: %s %s ..." % (method, log_url))

        def response_json():
            try:
                return response.json()
            except ValueError:
                testing.logger.debug("Response body: %r", response.text)
                raise Error(method, full_path, message="malformed response (not JSON)")

        if expect_access_denied:
            expected_http_status = [403]

        if isinstance(expected_http_status, int):
            expected_http_status = [expected_http_status]

        try:
            if response.status_code not in expected_http_status:
                if response.status_code in (400, 403, 404):
                    try:
                        error = response_json()["error"]
                    except Error:
                        testing.logger.exception("Unexpected response")
                    except KeyError:
                        testing.logger.error("Malformed JSON error response")
                    else:
                        testing.logger.error(
                            "JSON error:\n  Title: %s\n  Message: %s"
                            % (error["title"], error["message"])
                        )
                if response.status_code == 500:
                    testing.logger.error(response.content.decode())
                raise HTTPError(
                    method, full_path, expected_http_status, response.status_code
                )

            if response.status_code == 204:
                # No content.
                return None

            if response.status_code == 403:
                content_type = response.headers["Content-Type"]
                mime_type = content_type.partition(";")[0].strip()
                if mime_type == "text/plain":
                    if expect_access_denied == response.text:
                        return
                    raise AccessDenied(method, full_path, response.text)

            if expect_access_denied:
                raise Error(method, full_path, "access allowed unexpectedly")

            result = response_json()
        except testing.TestFailure as error:
            testing.logger.error(str(error))
            raise testing.TestFailure

        if expect is not None:
            testing.logger.debug("Checking JSON: %s" % log_url)

            errors = testing.expect.check_object(expect, result, path=path, silent=True)

            if errors:
                testing.logger.error(
                    "Wrong JSON received for %s:\n  %s" % (path, "\n  ".join(errors))
                )
                testing.logger.error("Received JSON: %s" % json.dumps(result, indent=2))
                testing.logger.error("".join(traceback.format_stack(limit=2)[:-2]))

                location = testing.expect.FailedCheck.current_location()
                if location:
                    testing.logger.error(
                        "Called from:\n  %s",
                        "\n  ".join(
                            f"{filename}:{linenr}" for filename, linenr in location
                        ),
                    )

            testing.logger.debug("Checked JSON: %s" % log_url)

        if extract is not None:
            path_element = r"\[(\d+)\]|(?:^|\.)(\w+)"

            def pick_single(what, data):
                assert isinstance(what, str)
                if not re.fullmatch(f"({path_element})+", what):
                    raise testing.Error(f"invalid `what` argument: {what!r}")
                for (index, key) in re.findall(path_element, what):
                    if index:
                        data = data[int(index)]
                    else:
                        data = data[key]
                return data

            def pick(what, data):
                if isinstance(what, (tuple, list, set)):
                    return type(what)(pick(element, data) for element in what)
                elif isinstance(what, dict):
                    assert len(what) == 1
                    for pick_from, pick_what in what.items():
                        return pick(pick_what, pick_single(pick_from, data))
                return pick_single(what, data)

            return pick(extract, result)

        return result

    @contextlib.contextmanager
    def cookie_session(self, signout):
        if self.current_session.sid is None:
            testing.expect.check("<signed in>", "<no session cookie received>")
        testing.logger.debug("Starting cookie session")
        try:
            yield
        finally:
            # Sign out unless we seem to have signed out already. Some tests may
            # want to do the signout explicitly, which is fine.
            if signout and self.current_session.sid is not None:
                try:
                    signout()
                except testing.TestFailure as failure:
                    if failure.message:
                        testing.logger.error(failure.message)
                except Exception:
                    testing.logger.exception("Failed to sign out!")

                if self.current_session.sid is not None:
                    testing.expect.check("<signed out>", "<session cookie not removed>")

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
        self.sessions.append(CookieSession())

    def validatelogin(self, username, password, expect_failure=False):
        data = {"fields": {"username": username, "password": password}}

        if expect_failure:
            expect = {"message": expect_failure}
        else:
            expect = {"message": None}

        self.operation("validatelogin", data=data, expect=expect)

    @contextlib.contextmanager
    def signin(
        self,
        username="admin",
        password="testing",
        use_httpauth=False,
        token=None,
        cached=True,
    ):
        if token:
            username = password = None
            use_httpauth = True
        if use_httpauth:
            self.sessions.append(
                HTTPAuthSession(username=username, password=password, token=token)
            )
            try:
                yield
            finally:
                self.sessions.pop()
        else:
            with self.no_session():
                self.collect_session_cookie()
                if cached and username in self.session_cookies:
                    self.sessions[-1].sid = self.session_cookies[username]
                    signout = None
                else:
                    self.json(
                        "sessions",
                        post={"username": username, "password": password},
                        expect={
                            "user": self.instance.userid(username),
                            "type": "normal",
                            "*": "*",
                        },
                    )
                    if cached:
                        self.session_cookies[username] = self.sessions[-1].sid
                        signout = None
                    else:

                        def signout():
                            self.json(
                                "sessions/current",
                                delete=True,
                                expected_http_status=204,
                            )

                with self.cookie_session(signout):
                    yield

    def run_basic_tests(self):
        self.json("users/me", expected_http_status=404)

        with self.signin("admin"):
            self.json(
                "users/me", expect={"id": self.instance.userid("admin"), "*": "*"}
            )
