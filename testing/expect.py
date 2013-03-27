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
import testing

class FailedCheck(testing.TestFailure):
    def __init__(self, expected, actual, message=None):
        if message is None:
            message = "check failed"
        super(FailedCheck, self).__init__("%s: expected=%r, actual=%r" % (message, expected, actual))
        self.expected = expected
        self.actual = actual

def simple_equal(expected, actual):
    return expected == actual

def check(expected, actual, equal=simple_equal, message=None):
    if not equal(expected, actual):
        raise FailedCheck(expected, actual, message=message)

def find_paleyellow(document, index):
    """Find index:th <table class="paleyellow"> in the document."""
    tables = document.findAll(
        "table", attrs={ "class": lambda value: "paleyellow" in value.split() })
    if index >= len(tables):
        raise FailedCheck("<table: index=%d>" % index,
                          "<no table: count=%d>" % len(tables))
    return tables[index]

def document_title(expected):
    """Return <title> checker."""
    return lambda document: check(expected, document.title.string)

def paleyellow_title(index, expected):
    """Return index:th <table class="paleyellow"> title checker."""
    def checker(document):
        table = find_paleyellow(document, index)
        actual = "<no title found>"
        h1 = table.find("h1")
        if h1 and h1.contents:
            actual = h1.contents[0]
        return check(expected, actual)
    return checker

def message_title(expected):
    """Return <div class="message"> title checker."""
    def checker(document):
        message = document.find(
            "div", attrs={ "class": lambda value: "message" in value.split() })
        actual = "<no message found>"
        if message:
            actual = "<no title found>"
            h1 = message.find("h1")
            if h1 and h1.contents:
                actual = h1.contents[0]
        return check(expected, actual)
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
