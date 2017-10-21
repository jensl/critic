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

import os
import sys

def detach(parent_exit_hook=lambda: 0):
    try:
        if os.fork() != 0:
            # Exit from parent process.
            sys.exit(parent_exit_hook())
    except OSError as error:
        print("fork failed: %s" % error.message, file=sys.stderr)
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        if os.fork() != 0:
            # Exit from parent process.
            sys.exit(0)
    except OSError as error:
        print("fork failed: %s" % error.message, file=sys.stderr)
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()

    stdin = open("/dev/null", "r")
    stdout = open("/dev/null", "a+")
    stderr = open("/dev/null", "a+")

    os.dup2(stdin.fileno(), sys.stdin.fileno())
    os.dup2(stdout.fileno(), sys.stdout.fileno())
    os.dup2(stderr.fileno(), sys.stderr.fileno())
