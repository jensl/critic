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

class Error(Exception):
    pass

class InstanceError(Error):
    """Error raised when VM instance is in unexpected/unknown state."""
    pass

class TestFailure(Error):
    """Error raised for "expected" test failures."""
    pass

import virtualbox
import frontend
import expect
import repository
import mailbox

_logging_configured = False

STDOUT = None
STDERR = None

def configureLogging(arguments=None):
    import logging
    import sys
    global _logging_configured, STDOUT, STDERR
    if not _logging_configured:
        # Essentially same as DEBUG, used when logging the output from commands
        # run in the guest system.
        STDOUT = logging.DEBUG + 1
        STDERR = logging.DEBUG + 2
        logging.addLevelName(STDOUT, "STDOUT")
        logging.addLevelName(STDERR, "STDERR")
        logging.basicConfig(
            format="%(asctime)-15s | %(levelname)-7s | %(message)s",
            stream=sys.stdout)
        logger = logging.getLogger("critic")
        level = logging.INFO
        if arguments:
            if getattr(arguments, "debug", False):
                level = logging.DEBUG
            elif getattr(arguments, "quiet", False):
                level = logging.WARNING
        logger.setLevel(level)
        _logging_configured = True
    else:
        logger = logging.getLogger("critic")
    return logger

def pause(prompt="Press ENTER to continue: "):
    print
    try:
        raw_input(prompt)
    except KeyboardInterrupt:
        print
        print
        raise
    print
