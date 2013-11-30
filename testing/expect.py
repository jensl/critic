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

import re
import traceback

import testing

def extract_text(source):
    result = u""
    if source:
        if isinstance(source, list):
            for element in source:
                result += extract_text(element)
        elif isinstance(source, basestring):
            result += source
        elif getattr(source, "string"):
            result += source.string
        elif getattr(source, "contents"):
            result += extract_text(source.contents)
        else:
            result += "[%r]" % source
    return result

class FailedCheck(testing.TestFailure):
    def __init__(self, expected, actual, location=None, message=None):
        if message is None:
            message = "check failed"
        if location is not None:
            message += ":\n At %s:%d" % location[0]
            for filename, linenr in location[1:]:
                message += ",\n   called from %s:%d" % (filename, linenr)
        super(FailedCheck, self).__init__("%s:\n  Expected: %r,\n  Actual:   %r"
                                          % (message, expected, actual))
        self.expected = expected
        self.actual = actual

def simple_equal(expected, actual):
    return expected == actual

def check(expected, actual, equal=simple_equal, message=None):
    if not equal(expected, actual):
        location = []
        for filename, linenr, _, _ in reversed(traceback.extract_stack()):
            if filename.startswith("testing/tests/"):
                location.append((filename[len("testing/tests/"):], linenr))
            elif location:
                break
        else:
            location = None
        raise FailedCheck(expected, actual, location=location, message=message)

def with_class(*names):
    def check(value):
        if value is None:
            return False
        tokens = set(value.split())
        for name in names:
            if name not in tokens:
                return False
        return True
    return { "class": check }

def find_paleyellow(document, index):
    """Find index:th ".paleyellow" in the document."""
    tables = document.findAll(attrs=with_class("paleyellow"))
    if index >= len(tables):
        raise FailedCheck("<paleyellow: index=%d>" % index,
                          "<no paleyellow: count=%d>" % len(tables))
    return tables[index]

def document_title(expected):
    """Return <title> checker."""
    return lambda document: check(expected, document.title.string)

def paleyellow_title(index, expected):
    """Return index:th ".paleyellow" title checker."""
    def checker(document):
        table = find_paleyellow(document, index)
        actual = "<no title found>"
        h1 = table.find("h1")
        if h1 and h1.contents:
            actual = h1.contents[0]
        return check(expected, actual)
    return checker

def message(expected_title, expected_body):
    """Return <div class="message"> title checker."""
    def checker(document):
        message = document.find(
            "div", attrs={ "class": lambda value: "message" in value.split() })
        actual_title = None
        actual_body = None
        if message:
            title = message.find("h1")
            actual_title = extract_text(title)
            if expected_body is not None:
                body = title.nextSibling
                actual_body = ""
                while body is not None:
                    if body:
                        actual_body += extract_text(body)
                    body = body.nextSibling
        if not actual_title:
            actual_title = "<no message title found>"
        check(expected_title, actual_title, message="title check failed")
        if expected_body is not None:
            if not actual_body:
                actual_body = "<no message body found>"
            check(expected_body, actual_body, message="body check failed")
    return checker

def message_title(expected_title):
    return message(expected_title, None)

def no_message():
    """Return negative <div class="message"> checker."""
    def checker(document):
        message = document.find(
            "div", attrs={ "class": lambda value: "message" in value.split() })
        if message:
            actual = "<message: %s>" % message.find("h1").contents[0]
        else:
            actual = "<no message found>"
        return check("<no message found>", actual)
    return checker

def pageheader_links(*scopes):
    scopes = set(scopes)
    expected = []
    for label, scope in [("Home", "authenticated"),
                         ("Dashboard", None),
                         ("Branches", None),
                         ("Search", None),
                         ("Services", "administrator"),
                         ("Repositories", "administrator"),
                         ("Extensions(?: \\(\\d+\\))?", "extensions"),
                         ("Config", None),
                         ("Tutorial", None),
                         ("News(?: \\(\\d+\\))?", None),
                         ("Sign in", "anonymous"),
                         ("Sign out", "authenticated"),
                         ("Back to Review", "review")]:
        if scope is None or scope in scopes:
            expected.append(label)
    def checker(document):
        pageheader = document.find("table", attrs={ "class": "pageheader" })
        actual = []
        for link in pageheader.find("ul").findAll("a"):
            actual.append(link.string)
        return check(",".join(expected), ",".join(actual), equal=re.match)
    return checker

def script_user(username):
    def checker(document):
        for script in document.findAll("script"):
            if script.string:
                match = re.match('var user = new User\\(\d+,\s*"([^"]+)"', script.string)
                if match:
                    return check(username, match.group(1))
        raise FailedCheck(username, "<no user found>")
    return checker

def script_anonymous_user():
    def checker(document):
        for script in document.findAll("script"):
            if script.string and script.string.startswith("var user = new User(null,"):
                return
        raise FailedCheck("<anonymous user>", "<no user found>")
    return checker

def script_no_user():
    def checker(document):
        for script in document.findAll("script"):
            if script.string and script.string.startswith("var user = new User("):
                raise FailedCheck("<no user found>", "<user found>")
    return checker
