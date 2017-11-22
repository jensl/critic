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

import sys
import os

# Try to import the readline module to augment input(), used below, which
# automatically uses readline for line editing if it has been loaded.  We don't
# really care if it fails; that just means input() is a bit dumber.
try:
    import readline
except:
    pass

__doc__ = "Helper functions for prompting for and reading input."


def apply_check(check, value):
    result = check(value)
    if result is None:
        return True
    elif result is True:
        print("Invalid input.")
        print()
    else:
        print("Invalid input: %s." % result)
        print()
    return False


def yes_or_no(prompt, default=None):
    prompt = "%s [%s/%s] " % (
        prompt,
        "Y" if default is True else "y",
        "N" if default is False else "n",
    )

    while True:
        try:
            value = input(prompt)
        except KeyboardInterrupt:
            print()
            raise

        if value.lower() in ("y", "yes"):
            return True
        elif value.lower() in ("n", "no"):
            return False
        elif value or default is None:
            print("Please answer 'y'/'yes' or 'n'/'no'.")
            print()
        else:
            return default


def string(prompt, default=None, check=None):
    prompt = "%s%s " % (prompt, (" [%s]" % default) if default is not None else "")

    while True:
        try:
            value = input(prompt)
        except KeyboardInterrupt:
            print()
            raise

        if default and not value:
            value = default

        if check:
            if apply_check(check, value):
                return value
        elif not value:
            print("Invalid input: empty.")
        else:
            return value


def password(prompt, default=None, twice=True):
    import termios

    prompt = "%s%s " % (prompt, " [****]" if default is not None else "")

    def internal(prompt):
        if os.isatty(sys.stdin.fileno()):
            old = termios.tcgetattr(sys.stdin)
            new = old[:]
            new[3] = new[3] & ~termios.ECHO
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new)
                try:
                    password = input(prompt)
                except KeyboardInterrupt:
                    print()
                    raise
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        else:
            password = sys.stdin.readline().rstrip("\n")
        print()
        if default and not password:
            return default
        else:
            return password

    while True:
        password = internal(prompt)

        if twice:
            andagain = internal("And again: ")

            if password == andagain:
                return password
            else:
                print()
                print("Passwords differ.  Please try again.")
                print()
        else:
            return password
