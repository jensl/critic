# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

# mypy; ignore-errors

import argparse
import importlib
import sys
import logging

parser = argparse.ArgumentParser()

parser.add_argument("--coverage", action="store_true")
parser.add_argument("test_module")
parser.add_argument("test_arguments", nargs=argparse.REMAINDER)

arguments = parser.parse_args()

if arguments.coverage:
    from coverage import call
else:

    def call(_, fn, *args, **kwargs):
        fn(*args, **kwargs)


def execute(module, argv):
    """Load |path| and call main() in it with |argv| as arguments

       If there is no main(), instead assume that each argument in |argv| is the
       name of a test, and run each test by calling a function named the same as
       the test, with no arguments."""

    logging.basicConfig(level=logging.DEBUG)

    module = importlib.import_module(module)

    if hasattr(module, "main"):
        module.main(argv)
        return

    for test in argv:
        if hasattr(module, test):
            getattr(module, test)()


try:
    call("unittest", execute, arguments.test_module, arguments.test_arguments)
    sys.exit(0)
except Exception:
    import traceback

    traceback.print_exc()
    sys.exit(1)
