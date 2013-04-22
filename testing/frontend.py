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

import logging
import json
import testing

try:
    import requests
    import BeautifulSoup
except ImportError:
    # testing/main.py detects and abort if either of these are missing, so just
    # ignore errors here.
    pass

logger = logging.getLogger("critic")

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

class Context(object):
    def __init__(self, finish):
        self.finish = finish
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.finish()
        return False

class Frontend(object):
    def __init__(self, hostname, http_port=8080):
        self.hostname = hostname
        self.http_port = http_port
        self.session_id = None

    def page(self, url, params={}, expect={}, expected_http_status=200):
        full_url = "http://%s:%d/%s" % (self.hostname, self.http_port, url)

        logger.debug("Fetching page: %s ..." % full_url)

        headers = {}

        if self.session_id:
            headers["Cookie"] = "sid=%s" % self.session_id

        response = requests.get(full_url,
                                params=params,
                                headers=headers)

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
            logger.error("Page '%s': %s" % (url, error.message))
            raise testing.TestFailure

        if response.status_code >= 400 and 200 in expected_http_status:
            # The caller expected a successful load or an error.  Signal errors
            # by returning None.
            return None

        document = BeautifulSoup.BeautifulSoup(text(response))

        logger.debug("Fetched page: %s" % full_url)
        logger.debug("Checking page: %s ..." % full_url)

        failed_checks = False

        for key, check in expect.items():
            try:
                check(document)
            except testing.expect.FailedCheck as failed_check:
                logger.error("Page '%s', test '%s': %s"
                             % (url, key, failed_check.message))
                failed_checks = True
            except Exception as error:
                raise Error(url, "'%s' checker failed: %s" % (key, str(error)))

        if failed_checks:
            raise testing.TestFailure

        logger.debug("Checked page: %s ..." % full_url)

        return document

    def operation(self, url, data, expect={}):
        full_url = "http://%s:%d/%s" % (self.hostname, self.http_port, url)

        logger.debug("Executing operation: %s ..." % full_url)

        headers = {}

        if self.session_id:
            headers["Cookie"] = "sid=%s" % self.session_id

        response = requests.post(full_url,
                                 data=json.dumps(data),
                                 headers=headers)

        try:
            if response.status_code != 200:
                raise HTTPError(url, 200, response.status_code)

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
            logger.error("Operation '%s': %s" % (url, error.message))
            raise testing.TestFailure

        if "sid" in response.cookies:
            logger.debug("Cookie: sid=%s" % response.cookies["sid"])
            self.session_id = response.cookies["sid"]

        logger.debug("Executed operation: %s" % full_url)
        logger.debug("Checking operation: %s" % full_url)

        # Check result["status"] first; if it doesn't have the expected value,
        # it's likely all other expected keys are simply missing from the
        # result, and thus produce rather meaningless errors.
        expected = expect.get("status", "ok")
        actual = result.get("status")
        if actual != expected:
            logger.error("Operation '%s', key 'status': check failed: expected=%r, actual=%r"
                         % (url, expected, actual))
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
                    logger.error("Operation '%s', key '%s': check failed: expected=%r, actual=%r"
                                 % (url, key, expected, actual))
                    failed_checks = True

        if failed_checks:
            raise testing.TestFailure

        logger.debug("Checked operation: %s" % full_url)

        return result

    def signin(self, username="admin", password="testing"):
        self.operation("validatelogin", data={ "username": username,
                                               "password": password })
        return Context(self.signout)

    def signout(self):
        try:
            self.operation("endsession", data={})
        except testing.TestFailure as failure:
            if failure.message:
                logger.error(failure.message)
        except Exception:
            logger.exception("Failed to sign out!")

        # Resetting the cookie effectively signs out even if the "endsession"
        # operation failed.
        self.session_id = None

    def run_basic_tests(self):
        # The /tutorials page is essentially static content and doesn't require
        # a signed in user, so a good test-case for checking if the site is up
        # and accessible at all.
        self.page("tutorial", expect={ "document_title": testing.expect.document_title(u"Tutorials"),
                                       "content_title": testing.expect.paleyellow_title(0, u"Tutorials") })

        # The /validatelogin operation is a) necessary for most meaningful
        # additional testing, and a simple enough operation to test.
        with self.signin():
            # Load /home to determine whether /validatelogin successfully signed in
            # (and that we stored the session id cookie correctly.)
            self.page("home", expect={ "document_title": testing.expect.document_title(u"Testing Administrator's Home"),
                                       "content_title": testing.expect.paleyellow_title(0, u"Testing Administrator's Home") })
