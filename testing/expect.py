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

def deunicode(v):
    if type(v) == unicode: return v.encode("utf-8")
    elif type(v) == list: return map(deunicode, v)
    elif type(v) == dict: return dict([(deunicode(a), deunicode(b)) for a, b in v.items()])
    else: return v

class FailedCheck(testing.TestFailure):
    def __init__(self, expected, actual, location=None, message=None):
        if message is None:
            message = "check failed"
        if location is not None:
            message += ":\n At %s:%d" % location[0]
            for filename, linenr in location[1:]:
                message += ",\n   called from %s:%d" % (filename, linenr)
        super(FailedCheck, self).__init__(
            "%s:\n  Expected: %r,\n  Actual:   %r"
            % (message, expected, deunicode(actual)))
        self.expected = expected
        self.actual = actual

    @staticmethod
    def current_location():
        location = []
        for filename, linenr, _, _ in reversed(traceback.extract_stack()):
            if filename.startswith("testing/tests/"):
                location.append((filename[len("testing/tests/"):], linenr))
            elif location:
                break
        else:
            location = None
        return location

def simple_equal(expected, actual):
    return expected == actual

def equal(expected, actual, equal=simple_equal, message=None):
    if not equal(expected, actual):
        location = FailedCheck.current_location()
        raise FailedCheck(expected, actual, location=location, message=message)

def true(actual, message):
    if not (actual is True):
        location = FailedCheck.current_location()
        raise FailedCheck(True, actual, location=location, message=message)

def false(actual, message):
    if not (actual is False):
        location = FailedCheck.current_location()
        raise FailedCheck(False, actual, location=location, message=message)

def none(actual, message):
    if not (actual is None):
        location = FailedCheck.current_location()
        raise FailedCheck(None, actual, location=location, message=message)

# For backwards compatibility...
check = equal

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

def message(expected_title, expected_body, title_equal=simple_equal,
            body_equal=simple_equal):
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
                body = message.find("p")
                actual_body = extract_text(body)
        if not actual_title:
            actual_title = "<no message title found>"
        check(expected_title, actual_title, equal=title_equal,
              message="title check failed")
        if expected_body is not None:
            if not actual_body:
                actual_body = "<no message body found>"
            check(expected_body, actual_body, equal=body_equal,
                  message="body check failed")
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

def script_user(expected):
    def checker(document):
        for script in document.findAll("script"):
            if script.string:
                actual = testing.User.from_script(script.string)
                if actual:
                    testing.expect.equal(expected, actual)
                    return
        raise FailedCheck(expected, "<no user found>")
    return checker

def script_anonymous_user():
    return script_user(testing.User.anonymous())

def script_no_user():
    def checker(document):
        for script in document.findAll("script"):
            if script.string:
                actual = testing.User.from_script(script.string)
                if actual:
                    raise FailedCheck("<no user found>", actual)
    return checker
