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
import shutil
import subprocess
import tempfile


class Error(Exception):
    message = None


class InstanceError(Error):
    """Error raised when VM instance is in unexpected/unknown state."""

    pass


class TestFailure(Error):
    """Error raised for "expected" test failures."""

    pass


class CommandError(InstanceError):
    def __init__(self, argv, stdout, stderr=None, returncode=None):
        super(CommandError, self).__init__(
            "%s: %s" % (type(self).__name__, " ".join(argv))
        )
        self.argv = argv
        self.command = " ".join(argv)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class CriticctlError(TestFailure):
    """Error raised for failed criticctl usage."""

    def __init__(self, command, stdout, stderr=None):
        super(CriticctlError, self).__init__(
            "CriticctlError: %s\nOutput:\n%s" % (command, stderr or stdout)
        )
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


class NotSupported(Error):
    """Error raised when a test is unsupported."""

    pass


class User(object):
    RE_DEFINITION = re.compile("var user = new User\\(([^,]+), ([^,]+),")

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

    @property
    def email(self):
        return f"{self.name}@example.org"


class Repository:
    def __init__(self, **data):
        self.id = data["id"]
        self.name = data["name"]


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

    users_to_add = {"admin"}

    def __init__(self):
        self.resetusers()
        self.__repositories = []
        self.__repository_map = {}
        self.__state_dir = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.__state_dir is not None:
            shutil.rmtree(self.__state_dir)
        return False

    @property
    def state_dir(self):
        if self.__state_dir is None:
            self.__state_dir = tempfile.mkdtemp()
        return self.__state_dir

    def resetusers(self):
        self.__users = []
        self.__user_map = {}

    def adduser(
        self, name, *, email=None, fullname=None, password=None, use_http=False
    ):
        if name in self.__user_map:
            return

        if email is None:
            email = "%s@example.org" % name
        if fullname is None:
            if name == "admin":
                fullname = "Testing Administrator"
            else:
                fullname = "%s von Testing" % name.capitalize()
        if password is None:
            password = "testing"

        if name == "admin":
            roles = ["administrator", "repositories", "newswriter", "developer"]
        elif name == "howard":
            roles = ["newswriter"]
        else:
            roles = []

        if getattr(self, "legacy_installed", False):
            self.criticctl(
                [
                    "adduser",
                    "--name",
                    name,
                    "--fullname",
                    fullname,
                    "--email",
                    email,
                    "--password",
                    password,
                ]
            )

            for role in roles:
                self.criticctl(["addrole", "--name", name, "--role", role])
        elif use_http:
            self.frontend.json(
                "users",
                post={
                    "name": name,
                    "fullname": fullname,
                    "email": email,
                    "password": password,
                    "roles": roles,
                },
            )
        else:
            role_args = []
            for role in roles:
                role_args.extend(["--role", role])

            self.criticctl(
                [
                    "adduser",
                    "--username",
                    name,
                    "--fullname",
                    fullname,
                    "--email",
                    email,
                    "--password",
                    password,
                ]
                + role_args
            )

        return self.registeruser(name)

    def registeruser(self, name):
        user_id = len(self.__users) + 1
        user = User(user_id, name)
        self.__users.append(user)
        self.__user_map[user_id] = user
        self.__user_map[name] = user
        return user

    def renameuser(self, old_name, new_name):
        user = self.__user_map[old_name]
        del self.__user_map[old_name]
        user.name = new_name
        self.__user_map[new_name] = user

    def user(self, key):
        return self.__user_map[key]

    def userid(self, name):
        return self.user(name).id

    def register_repository(self, repository_data):
        repository = Repository(**repository_data)
        self.__repositories.append(repository)
        self.__repository_map[repository.id] = repository
        self.__repository_map[repository.name] = repository

    def repository(self, key):
        return self.__repository_map[key]

    def filter_service_log(self, service_name, level="warning"):
        data = self.filter_service_logs(level, [service_name])
        return data.get(service_name, [])

    @property
    def running_services(self):
        return [
            "branchtracker",
            "branchupdater",
            "differenceengine",
            "githook",
            "maildelivery",
            "maintenance",
            "reviewupdater",
            "servicemanager",
        ]

    def check_service_logs(self, level="warning"):
        data = self.filter_service_logs(level, self.running_services)
        if not data:
            return
        for service_name, entries in data.items():
            lines = "\n".join(entries)
            logger.error(
                "%s: service log contains unexpected entries:\n  %s"
                % (service_name, "\n  ".join(lines.splitlines()))
            )

    def synchronize_service(self, *service_names, force_maintenance=False, timeout=30):
        args = ["--timeout", str(timeout)]
        if force_maintenance:
            args.append("--run-maintenance-tasks")
        args.extend(service_names)
        self.criticctl(["synchronize-service"] + args)

    def executeProcess(self, args, log_stdout=True, log_stderr=True, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        try:
            process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
            )
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

    def translateUnittestModule(self, module):
        path = module.split(".")
        if path[0] == "api":
            # API unittests are under api/impl/.
            path.insert(1, "impl")
        if os.path.isdir(os.path.join("critic", *path)):
            path.append("unittest")
        else:
            path[-1] += "_unittest"
        return ".".join(["critic"] + path)

    def unittest(self, module, tests, args=None):
        translated_module = self.translateUnittestModule(module)
        if not args:
            args = []
        for test in tests:
            logger.info("Running unit test: %s (%s)" % (module, test))
            try:
                output = self.run_unittest([translated_module] + args + [test])
                lines = output.strip().splitlines()
                expected = test + ": ok"
                matching = list(filter(lambda line: line == expected, lines))
                if len(lines) == 0:
                    logger.warning("No unit test output: %s (%s)")
                elif len(matching) == 0:
                    logger.warning(
                        "No unit test confirmation (but some output): %s (%s)"
                        % (module, test)
                    )
                elif len(matching) > 1:
                    logger.warning(
                        "Multiple unit test confirmations: %s (%s)" % (module, test)
                    )
                if lines and (lines[-1] != expected):
                    logger.warning(
                        "Unit test's last line of output isn't unit test confirmation: %s (%s)"
                        % (module, test)
                    )
                if len(lines) > 0:
                    [logger.info(line) for line in lines[:-1]]
            except CommandError as error:
                output = "\n  ".join(error.stderr.splitlines())
                logger.error(
                    "Unit tests failed: %s: %s\nCommand: %s\nOutput:\n  %s"
                    % (module, test, error.command, output)
                )

    def home_dir(self, *, for_user):
        return os.path.join(self.state_dir, for_user)

    def ssh_key(self, *, for_user, key_type="rsa"):
        ssh_dir = os.path.join(self.home_dir(for_user=for_user), ".ssh")
        if not os.path.isdir(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
        private_key = os.path.join(ssh_dir, f"id_{key_type}")
        if not os.path.isfile(private_key):
            execute.execute(["ssh-keygen", "-t", key_type, "-f", private_key, "-N", ""])
            with open(private_key + ".pub") as file:
                key_type, key, comment = file.read().split(" ")
            with self.frontend.signin(for_user):
                self.frontend.json(
                    "users/me/usersshkeys",
                    post={"type": key_type, "key": key, "comment": comment},
                )
        return private_key

    def ssh_config(self, *, for_user):
        sshd_hostname, sshd_port = self.sshd_address()
        ssh_dir = os.path.join(self.home_dir(for_user=for_user), ".ssh")
        if not os.path.isdir(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
        config_filename = os.path.join(ssh_dir, "config")
        if not os.path.isfile(config_filename):
            with open(config_filename, "w") as config_file:
                print(
                    f"IdentityFile {self.ssh_key(for_user=for_user)}",
                    f"UserKnownHostsFile {self.ssh_known_hosts()}",
                    f"Host critic",
                    f"  Hostname {sshd_hostname}",
                    f"  Port {sshd_port}",
                    sep="\n",
                    file=config_file,
                )
        return config_filename

    def ssh_known_hosts(self):
        return os.path.join(self.state_dir, "ssh_known_hosts")


from . import docker
from . import execute
from . import expect
from . import findtests
from . import frontend
from . import local
from . import mailbox
from . import quickstart
from . import repository
from . import utils
from . import virtualbox

__all__ = [
    "docker",
    "execute",
    "expect",
    "findtests",
    "frontend",
    "local",
    "mailbox",
    "quickstart",
    "repository",
    "utils",
    "virtualbox",
]

logger = None

STREAM = None
STDOUT = None
STDERR = None


def configureLogging(arguments=None, wrap=None):
    import logging
    import sys

    try:
        from critic.base.coloredlog import Formatter

        if not Formatter.is_supported():
            raise ImportError()
    except ImportError:
        from logging import Formatter

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
        if "CODEBUILD_BUILD_ID" in os.environ:
            log_format = "%(levelname)-7s - %(message)s"
        else:
            log_format = "%(asctime)-15s | %(levelname)-7s | %(message)s"
        handler = logging.StreamHandler(STREAM)
        handler.setFormatter(Formatter(log_format))
        logger = logging.getLogger("critic")
        logger.addHandler(handler)
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
        print(prompt, end=" ", file=STREAM)
        action = input()
    except KeyboardInterrupt:
        print(file=STREAM)
        print(file=STREAM)
        return "stop"
    print(file=STREAM)
    return action


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
                [
                    "git",
                    "grep",
                    "--quiet",
                    "-e",
                    "--minimum-password-hash-time",
                    commit,
                    "--",
                    "installation/config.py",
                ]
            )
        except subprocess.CalledProcessError:
            return False
        else:
            return True
    else:
        return exists_at(commit, "testing/flags/%s.flag" % flag)


AFTER_TEST = []


def after_test(fn, *args, **kwargs):
    AFTER_TEST.append((fn, args, kwargs))
