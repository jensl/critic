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

import sys

import inpututils

headless = False

def yes_or_no(prompt, default=None):
    if headless:
        if default is None:
            print """
ERROR: yes/no input requested in headless mode!
  Prompt: %s
""" % prompt
            sys.exit(1)
        else:
            print "%s %s" % (prompt, "y" if default else "n")
            return default

    return inpututils.yes_or_no(prompt, default)

def string(prompt, default=None, check=None):
    if headless:
        if default is None:
            print """
ERROR: string input requested in headless mode!
  Prompt: %s
""" % prompt
            sys.exit(1)
        else:
            print "%s %s" % (prompt, default)
            return default

    return inpututils.string(prompt, default, check)

def password(prompt, default=None, twice=True):
    if headless:
        if default is None:
            print """
ERROR: password input requested in headless mode!
  Prompt: %s
""" % prompt
            sys.exit(1)
        else:
            print "%s %s" % (prompt, "****")
            return default

    return inpututils.password(prompt, default, twice)
