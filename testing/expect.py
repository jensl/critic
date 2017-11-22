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
import os
import traceback

import testing


def extract_text(source):
    result = ""
    if source:
        if isinstance(source, list):
            for element in source:
                result += extract_text(element)
        elif isinstance(source, str):
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
        super(FailedCheck, self).__init__(
            "%s:\n  Expected: %r,\n  Actual:   %r" % (message, expected, actual)
        )
        self.expected = expected
        self.actual = actual

    @staticmethod
    def current_location():
        location = []
        for filename, linenr, _, _ in reversed(traceback.extract_stack()):
            if filename.startswith(f"{os.path.dirname(__file__)}/tests/"):
                location.append(
                    (filename[len(f"{os.path.dirname(__file__)}/tests/") :], linenr)
                )
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


def true(actual, message=None):
    if not (actual is True):
        location = FailedCheck.current_location()
        raise FailedCheck(True, actual, location=location, message=message)


def false(actual, message=None):
    if not (actual is False):
        location = FailedCheck.current_location()
        raise FailedCheck(False, actual, location=location, message=message)


def none(actual, message=None):
    if not (actual is None):
        location = FailedCheck.current_location()
        raise FailedCheck(None, actual, location=location, message=message)


# For backwards compatibility...
check = equal


def check_object(expected, actual, *, path="<actual>", silent=False):
    errors = []

    def describe(value):
        if isinstance(value, dict) or value is dict:
            return "object"
        if isinstance(value, list) or value is list:
            return "array"
        if isinstance(value, set):
            return "one of: " % ",".join(sorted(value))
        if isinstance(value, type):
            return {int: "integer", float: "float", str: "string"}[value]
        if isinstance(value, (str, int, float)):
            return repr(value)
        if value is None:
            return "null"
        return "unexpected"

    def check_object(path, expected, actual, *, allow_additional=False):
        if not isinstance(actual, dict):
            errors.append("%s: value is %s, expected object" % (path, describe(actual)))
            return
        if expected is dict:
            return
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        if "*" in expected_keys:
            expected_keys.remove("*")
            allow_additional = True
        if not allow_additional and actual_keys - expected_keys:
            errors.append(
                "%s: unexpected keys: %r" % (path, tuple(actual_keys - expected_keys))
            )
        if expected_keys - actual_keys:
            errors.append(
                "%s: missing keys: %r" % (path, tuple(expected_keys - actual_keys))
            )
        for key in sorted(expected_keys & actual_keys):
            do_check("%s/%s" % (path, key), expected[key], actual[key])

    def check_array(path, expected, actual):
        if not isinstance(actual, list):
            errors.append("%s: value is %s, expected array" % (path, describe(actual)))
        if expected is list:
            return
        if len(actual) != len(expected):
            errors.append(
                "%s: wrong array length: got %s, expected %s"
                % (path, len(actual), len(expected))
            )
            return
        for index, (expected, actual) in enumerate(zip(expected, actual)):
            do_check("%s[%d]" % (path, index), expected, actual)

    def check_set(path, expected, actual):
        if not isinstance(actual, str):
            errors.append("%s: value is %s, expected string" % (path, describe(actual)))
        if actual not in expected:
            errors.append(
                "%s: value is %s, expected %s"
                % (path, describe(actual), describe(expected))
            )

    def check_null(path, actual):
        if actual is not None:
            errors.append("%s: value is %s, expected null" % (path, describe(actual)))

    def check_value(path, expected, actual):
        if isinstance(actual, (dict, list)):
            errors.append(
                "%s: value is %s, expected %s"
                % (path, describe(actual), describe(expected))
            )
        if isinstance(expected, type):
            if not isinstance(actual, expected):
                errors.append(
                    "%s: wrong value: got %r, expected %r"
                    % (path, actual, describe(expected))
                )
        elif actual != expected:
            errors.append(
                "%s: wrong value: got %r, expected %r" % (path, actual, expected)
            )

    def check_regexp(path, expected, actual):
        if not isinstance(actual, str):
            errors.append("%s: value is %s, expected string", path, describe(actual))
        elif expected.match(actual) is None:
            errors.append(
                f"{path}: value is {describe(actual)}, "
                f"expected matching {expected.pattern}"
            )

    def do_check(path, expected, actual):
        errors_before = len(errors)
        if callable(expected) and not isinstance(expected, type):
            errors.extend(expected(path, actual, do_check) or ())
        elif isinstance(expected, dict) or expected is dict:
            check_object(path, expected, actual)
        elif isinstance(expected, list) or expected is list:
            check_array(path, expected, actual)
        elif isinstance(expected, set):
            check_set(path, expected, actual)
        elif hasattr(expected, "match") and callable(expected.match):
            check_regexp(path, expected, actual)
        elif expected is None:
            check_null(path, actual)
        else:
            check_value(path, expected, actual)
        return errors_before == len(errors)

    do_check(path, expected, actual)

    if errors and not silent:
        testing.logger.error("Incorrect object:\n  %s" % "\n  ".join(errors))
        testing.logger.error("Actual object: %s" % json.dumps(actual, indent=2))
        raise testing.TestFailure()

    return errors


class that:
    def __init__(self, actual_value):
        self.actual_value = actual_value

    def equals(self, expected_value, *, message=None):
        if self.actual_value != expected_value:
            raise FailedCheck(
                expected=expected_value,
                actual=self.actual_value,
                location=FailedCheck.current_location(),
                message=message,
            )
