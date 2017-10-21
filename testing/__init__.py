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

import os
import re
import subprocess

class Error(Exception):
    pass

class InstanceError(Error):
    """Error raised when VM instance is in unexpected/unknown state."""
    pass

class TestFailure(Error):
    """Error raised for "expected" test failures."""
    pass

class CommandError(InstanceError):
    def __init__(self, argv, stdout, stderr=None):
        self.argv = argv
        self.command = " ".join(argv)
        self.stdout = stdout
        self.stderr = stderr

class CriticctlError(TestFailure):
    """Error raised for failed criticctl usage."""
    def __init__(self, command, stdout, stderr=None):
        super(CriticctlError, self).__init__(
            "CriticctlError: %s\nOutput:\n%s" % (command, stderr or stdout))
        self.command = command
        self.stdout = stdout
        self.stderr = stderr

class NotSupported(Error):
    """Error raised when a test is unsupported."""
    pass

class User(object):
    RE_DEFINITION = re.compile('var user = new User\\(([^,]+), ([^,]+),')

    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name

    def __eq__(self, other):
        if isinstance(other, User):
            return self.id == other.id and self.name == other.name
        return False

    def __repr__(self):
        if self.id is None:
            return "<anonymous user>"
        return "<user '%(name)s' (%(id)d)>" % self

    @staticmethod
    def from_script(script):
        match = User.RE_DEFINITION.match(script)
        if match:
            if match.groups() == ("null", "null"):
                return User.anonymous()
            return User(int(match.group(1)), eval(match.group(2)))

    @staticmethod
    def anonymous():
        return User(None, None)

class Instance(object):
    flags_on = []
    flags_off = []

    # The VirtualBox instance sets this depending on arguments. Other modes
    # don't support it, so default to False.
    test_extensions = False

    # This is used to keep track of which commit is currently running.  This is
    # really only relevant for VM instances when upgrading from an older commit,
    # so only testing.virtualbox.Instance actually sets this.
    current_commit = None

    def __init__(self):
        self.resetusers()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def resetusers(self):
        self.__users = []
        self.__user_map = {}

    def registeruser(self, name):
        user_id = len(self.__users) + 1
        user = User(user_id, name)
        self.__users.append(user)
        self.__user_map[user_id] = user
        self.__user_map[name] = user

    def user(self, key):
        return self.__user_map[key]

    def userid(self, name):
        return self.user(name).id

    def filter_service_log(self, service_name, level="warning"):
        data = self.filter_service_logs(level, [service_name])
        if data is None:
            return []
        return data.get(service_name)

    def check_service_logs(self, level="warning"):
        data = self.filter_service_logs(level, ["branchtracker",
                                                "changeset",
                                                "githook",
                                                "highlight",
                                                "maildelivery",
                                                "maintenance",
                                                "servicemanager",
                                                "watchdog"])
        if data is None:
            return
        for service_name, entries in data.items():
            lines = "\n".join(entries)
            logger.error(
                "%s: service log contains unexpected entries:\n  %s"
                % (service_name, "\n  ".join(lines.splitlines())))

    def executeProcess(self, args, log_stdout=True, log_stderr=True, **kwargs):
        try:
            process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        except OSError as error:
            raise CommandError(args, None, str(error))
        stdout, stderr = process.communicate()
        if stdout.strip() and log_stdout:
            logger.log(STDOUT, stdout.rstrip("\n"))
        if stderr.strip() and log_stderr:
            logger.log(STDERR, stderr.rstrip("\n"))
        if process.returncode != 0:
            raise CommandError(args, stdout, stderr)
        return stdout

    def translateUnittestPath(self, module):
        path = module.split(".")
        if path[0] == "api":
            # API unittests are under api/impl/.
            path.insert(1, "impl")
        path = os.path.join(*path)
        if os.path.isdir(os.path.join("src", path)):
            path = os.path.join(path, "unittest.py")
        else:
            path += "_unittest.py"
        return path

    def unittest(self, module, tests, args=None):
        path = self.translateUnittestPath(module)
        if not args:
            args = []
        for test in tests:
            logger.info("Running unit test: %s (%s)" % (module, test))
            try:
                output = self.run_unittest([path] + args + [test])
                lines = output.strip().splitlines()
                expected = test + ": ok"
                matching = filter(lambda line: line == expected, lines)
                if len(lines) == 0:
                    logger.warning("No unit test output: %s (%s)")
                elif len(matching) == 0:
                    logger.warning("No unit test confirmation (but some output): %s (%s)"
                                   % (module, test))
                elif len(matching) > 1:
                    logger.warning("Multiple unit test confirmations: %s (%s)"
                                   % (module, test))
                if lines and (lines[-1] != expected):
                    logger.warning("Unit test's last line of output isn't unit test confirmation: %s (%s)"
                                   % (module, test))
                if len(lines) > 0:
                    [logger.info(line) for line in lines[:-1]]
            except CommandError as error:
                output = "\n  ".join(error.stderr.splitlines())
                logger.error(
                    "Unit tests failed: %s: %s\nCommand: %s\nOutput:\n  %s"
                    % (module, test, error.command, output))

import local
import virtualbox
import frontend
import expect
import repository
import mailbox
import findtests
import utils
import quickstart
import execute

logger = None

STREAM = None
STDOUT = None
STDERR = None

def configureLogging(arguments=None, wrap=None):
    import logging
    import sys
    global logger, STREAM, STDOUT, STDERR
    if not logger:
        # Essentially same as DEBUG, used when logging the output from commands
        # run in the guest system.
        STDOUT = logging.DEBUG + 1
        STDERR = logging.DEBUG + 2
        logging.addLevelName(STDOUT, "STDOUT")
        logging.addLevelName(STDERR, "STDERR")
        if arguments and getattr(arguments, "coverage", False):
            STREAM = sys.stderr
        else:
            STREAM = sys.stdout
        logging.basicConfig(
            format="%(asctime)-15s | %(levelname)-7s | %(message)s",
            stream=STREAM)
        logger = logging.getLogger("critic")
        level = logging.INFO
        if arguments:
            if getattr(arguments, "debug", False):
                level = logging.DEBUG
            elif getattr(arguments, "quiet", False):
                level = logging.WARNING
        logger.setLevel(level)
        if wrap:
            logger = wrap(logger)
    return logger

def pause(prompt="Press ENTER to continue: "):
    print(file=STREAM)
    try:
        print(prompt, end=' ', file=STREAM)
        raw_input()
    except KeyboardInterrupt:
        print(file=STREAM)
        print(file=STREAM)
        raise
    print(file=STREAM)

class Context(object):
    def __init__(self, start, finish):
        self.start = start
        self.finish = finish
    def __enter__(self):
        self.start()
        return self
    def __exit__(self, *args):
        self.finish()
        return False

def exists_at(commit, path):
    lstree = subprocess.check_output(["git", "ls-tree", commit, path])
    return bool(lstree.strip())

def has_flag(commit, flag):
    if flag == "minimum-password-hash-time":
        try:
            subprocess.check_call(
                ["git", "grep", "--quiet", "-e", "--minimum-password-hash-time",
                 commit, "--", "installation/config.py"])
        except subprocess.CalledProcessError:
            return False
        else:
            return True
    else:
        return exists_at(commit, "testing/flags/%s.flag" % flag)
