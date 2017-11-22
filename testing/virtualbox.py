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

import datetime
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time

import testing

# Directory (on guest system) to store coverage data in.
COVERAGE_DIR = "/var/tmp/critic/coverage"


class HostCommandError(testing.CommandError):
    pass


class GuestCommandError(testing.CommandError):
    pass


class Instance(testing.Instance):
    def __init__(
        self, arguments, install_commit=None, upgrade_commit=None, frontend=None
    ):
        super(Instance, self).__init__()
        self.arguments = arguments
        self.vboxhost = getattr(arguments, "runner_hostname", "host")
        self.identifier = arguments.vm_identifier
        self.snapshot = arguments.vm_snapshot
        self.hostname = arguments.vm_hostname or self.identifier
        self.ssh_port = arguments.vm_ssh_port
        self.install_python = getattr(arguments, "vm_install_python", None)
        self.upgrade_python = getattr(arguments, "vm_upgrade_python", None)
        self.legacy_installing = False
        self.legacy_installed = None
        self.test_extensions = getattr(arguments, "test_extensions", None)
        if install_commit:
            self.install_commit, self.install_commit_description = install_commit
            self.tested_commit = self.install_commit
        if upgrade_commit:
            self.upgrade_commit, self.upgrade_commit_description = upgrade_commit
            if self.upgrade_commit:
                self.tested_commit = self.upgrade_commit
        self.frontend = frontend
        self.strict_fs_permissions = getattr(arguments, "strict_fs_permissions", False)
        self.coverage = getattr(arguments, "coverage", False)
        self.mailbox = None
        self.etc_dir = "/etc/critic"
        self.criticctl_path = None

        # Check that the identified VM actually exists:
        output = subprocess.check_output(
            ["VBoxManage", "list", "vms"], stderr=subprocess.STDOUT, encoding="utf-8"
        )
        if not self.__isincluded(output):
            raise testing.Error("Invalid VM identifier: %s" % self.identifier)

        self.check_snapshot(self.snapshot)

        # Check that the VM isn't running:
        state = self.state()
        if state != "poweroff":
            raise testing.Error("Invalid VM state: %s (expected 'poweroff')" % state)

        self.__reset()

    def __reset(self):
        self.__started = False
        self.__installed = False
        self.__upgraded = False
        self.__run_apt_update = True
        self.resetusers()
        self.registeruser("admin")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self.__started:
            self.stop()
        self.__reset()
        return super().__exit__(*exc_info)

    def __vmcommand(self, command, *arguments):
        argv = ["VBoxManage", command, self.identifier] + list(arguments)
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(
                argv, stderr=subprocess.STDOUT, encoding="utf-8"
            )
        except subprocess.CalledProcessError as error:
            raise HostCommandError(argv, error.output)

    def __isincluded(self, output):
        name = '"%s"' % self.identifier
        uuid = "{%s}" % self.identifier

        for line in output.splitlines():
            if name in line or uuid in line:
                return True
        else:
            return False

    @property
    def python(self):
        if self.__upgraded:
            return self.upgrade_python or "python3"
        if self.install_python is not None:
            return self.install_python
        if self.legacy_installing:
            return "python2.7"
        return "python3"

    def isrunning(self):
        output = subprocess.check_output(
            ["VBoxManage", "list", "runningvms"],
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
        return self.__isincluded(output)

    def state(self):
        output = self.__vmcommand("showvminfo", "--machinereadable")
        for line in output.splitlines():
            if line.startswith("VMState="):
                return eval(line[len("VMState=") :])
        return "<not found>"

    def count_snapshots(self, snapshot):
        try:
            output = subprocess.check_output(
                ["VBoxManage", "snapshot", self.identifier, "list"],
                stderr=subprocess.STDOUT,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError:
            # Assuming we've already checked that 'self.identifier' is a valid
            # VM identifier, the most likely cause of this failure is that the
            # VM has no snapshots.
            return 0
        else:
            name = f"Name: {snapshot} ("
            uuid = f"(UUID: {snapshot})"
            count = 0
            for line in output.splitlines():
                if name in line or uuid in line:
                    count += 1
            return count

    def check_snapshot(self, snapshot, *, allow_missing=False):
        # Check that the identified snapshot actually exists (and that there
        # aren't multiple snapshots with the same name):
        count = self.count_snapshots(snapshot)
        if count == 0:
            if allow_missing:
                return
            raise testing.Error(f"Invalid VM snapshot: {snapshot} (not found)")
        if count > 1:
            raise testing.Error(
                f"Invalid VM snapshot: {snapshot} (matches multiple snapshots)"
            )

    def wait(self):
        testing.logger.debug("Waiting for VM to come online ...")

        while True:
            try:
                connection = socket.create_connection(
                    (self.hostname, self.ssh_port), timeout=0.25
                )
            except OSError:
                time.sleep(0.25)
            else:
                connection.close()
                break

    def start(self):
        testing.logger.debug("Starting VM: %s ..." % self.identifier)

        self.__vmcommand("snapshot", "restore", self.snapshot)
        self.__vmcommand("startvm", "--type", "headless")
        self.__started = True

        self.wait()

        # Set the guest system's clock to match the host system's.  Since we're
        # restoring the same snapshot over and over, the guest system's clock is
        # probably quite far from the truth.
        now = datetime.datetime.utcnow().strftime("%m%d%H%M%Y.%S")
        self.execute(["sudo", "date", "--utc", now])

        testing.logger.info("Started VM: %s" % self.identifier)

    def stop(self):
        testing.logger.debug("Stopping VM: %s ..." % self.identifier)

        self.__vmcommand("controlvm", "poweroff")

        while self.state() != "poweroff":
            time.sleep(0.1)

        # It appears the VirtualBox "session" can be locked for a while after
        # the "controlvm poweroff" command, and possibly after the VM state
        # changes to "poweroff", so sleep a little longer to avoid problems.
        time.sleep(0.5)

        testing.logger.info("Stopped VM: %s" % self.identifier)

    def retake_snapshot(self, name):
        if self.count_snapshots(name) == 0:
            self.__vmcommand("snapshot", "take", name, "--pause")
            return "created"

        index = 1
        while True:
            temporary_name = "%s-%d" % (name, index)
            if self.count_snapshots(temporary_name) == 0:
                break
            index += 1

        self.__vmcommand("snapshot", "take", temporary_name, "--pause")
        self.__vmcommand("snapshot", "delete", name)
        self.__vmcommand("snapshot", "edit", temporary_name, "--name", name)
        return "updated"

    def execute(
        self,
        argv,
        *,
        cwd=None,
        timeout=None,
        interactive=False,
        as_user=None,
        log_stdout=True,
        log_stderr=True,
        stdin_data=None,
        mix_stdout_and_stderr=False,
    ):
        guest_argv = list(argv)
        if cwd is not None:
            guest_argv[:0] = ["cd", cwd, "&&"]
        host_argv = ["ssh"]
        if self.ssh_port != 22:
            host_argv.extend(["-p", str(self.ssh_port)])
        if timeout is not None:
            host_argv.extend(["-o", "ConnectTimeout=%d" % timeout])
        if not (interactive or stdin_data):
            host_argv.append("-n")
        if as_user is not None:
            host_argv.extend(["-l", as_user])
        host_argv.append(self.hostname)

        testing.logger.debug("Running: " + " ".join(host_argv + guest_argv))

        env = {
            key: value
            for key, value in os.environ.items()
            if key != "LANG" and not key.startswith("LC_")
        }

        try:
            return testing.execute.execute(
                host_argv + guest_argv,
                env=env,
                interactive=interactive,
                stdin_data=stdin_data,
                mix_stdout_and_stderr=mix_stdout_and_stderr,
            )
        except testing.CommandError as error:
            raise GuestCommandError(argv, error.stdout, error.stderr)

    def copyto(self, source, target, as_user=None):
        target = "%s:%s" % (self.hostname, target)
        if as_user:
            target = "%s@%s" % (as_user, target)
        argv = ["scp", "-q", "-P", str(self.ssh_port), source, target]
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(
                argv, stderr=subprocess.STDOUT, encoding="utf-8"
            )
        except subprocess.CalledProcessError as error:
            raise GuestCommandError(argv, error.output)

    def copyfrom(self, source, target, as_user=None):
        source = "%s:%s" % (self.hostname, source)
        if as_user:
            source = "%s@%s" % (as_user, source)
        argv = ["scp", "-q", "-P", str(self.ssh_port), source, target]
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(
                argv, stderr=subprocess.STDOUT, encoding="utf-8"
            )
        except subprocess.CalledProcessError as error:
            raise GuestCommandError(argv, error.output)

    def criticctl(self, arguments, *, stdin_data=None):
        if self.criticctl_path is None:
            testing.logger.error("Critic not installed yet!")
            return
        argv = ["sudo", "-H", self.criticctl_path]
        if not self.legacy_installed and self.arguments.debug:
            argv.append("--verbose")
        argv.extend(shlex.quote(argument) for argument in arguments)
        try:
            return self.execute(argv, stdin_data=stdin_data)
        except GuestCommandError as error:
            raise testing.CriticctlError(error.command, error.stdout, error.stderr)

    def adduser(self, name, email=None, fullname=None, password=None, roles=[]):
        super().adduser(name, email, fullname, password, roles)

        self.execute(
            [
                "sudo",
                "adduser",
                "--ingroup",
                "critic",
                "--disabled-password",
                "--gecos",
                "''",
                name,
            ]
        )

        # Running all commands with a single self.execute() call is just an
        # optimization; SSH sessions are fairly expensive to start.
        self.execute(
            [
                "sudo",
                "mkdir",
                ".ssh",
                "&&",
                "sudo",
                "cp",
                "$HOME/.ssh/authorized_keys",
                ".ssh/",
                "&&",
                "sudo",
                "chown",
                "-R",
                name,
                ".ssh/",
                "&&",
                "sudo",
                "-H",
                "-u",
                name,
                "git",
                "config",
                "--global",
                "user.name",
                f"'{fullname}'",
                "&&",
                "sudo",
                "-H",
                "-u",
                name,
                "git",
                "config",
                "--global",
                "user.email",
                email,
            ],
            cwd="/home/%s" % name,
        )

    def has_flag(self, flag):
        if self.upgrade_commit and self.__upgraded:
            check_commit = self.upgrade_commit
        else:
            check_commit = self.install_commit
        return testing.has_flag(check_commit, flag)

    def repository_path(self, repository="critic"):
        return "/var/git/%s.git" % repository

    def repository_url(self, name=None, repository="critic"):
        if name is None:
            user_prefix = ""
        else:
            user_prefix = name + "@"
        return "%s%s:/var/git/%s.git" % (user_prefix, self.hostname, repository)

    def restrict_access(self):
        if not self.strict_fs_permissions:
            return

        # Set restrictive access bits on home directory of the installing user
        # and of root, to make sure that no part of Critic's installation
        # process, or the background processes started by it, depend on being
        # able to access them as the Critic system user.
        self.execute(["sudo", "chmod", "-R", "go-rwx", "$HOME", "/root"])

        # Running install.py may have left files owned by root in $HOME.  The
        # command above will have made them inaccessible for sure, so change
        # the ownership back to us.
        self.execute(["sudo", "chown", "-R", "$LOGNAME", "$HOME"])

    def apt_install(self, *packages, upgrade=False):
        def run_apt(*args):
            while True:
                argv = [
                    "sudo",
                    "DEBIAN_FRONTEND=noninteractive",
                    "apt-get",
                    "-qq",
                ] + list(args)
                try:
                    return self.execute(argv)
                except GuestCommandError as error:
                    if "/var/lib/apt/lists/lock" in error.stderr:
                        testing.logger.debug("Apt locked: sleeping one second ...")
                        time.sleep(1)
                    else:
                        raise

        if self.__run_apt_update:
            run_apt("update")
            self.__run_apt_update = False

        assert packages or upgrade
        if not packages:
            run_apt("upgrade")
        else:
            run_apt("install", *packages)

    def install(self, repository, **kwargs):
        # First check Git version, and install if necessary.
        def git_version():
            output = self.execute(["git", "--version"]).strip()
            if output.startswith("git version "):
                return output[len("git version ") :]
            return output

        try:
            testing.logger.info("Existing Git: %s", git_version())
        except GuestCommandError:
            testing.logger.debug("Installing Git ...")

            self.apt_install("git-core")

            testing.logger.info("Installed Git: %s", git_version())

        self.execute(["git", "clone", repository.url, "critic"])
        self.execute(
            [
                "git",
                "fetch",
                "--quiet",
                "&&",
                "git",
                "checkout",
                "--quiet",
                self.install_commit,
            ],
            cwd="critic",
        )

        if self.has_flag("critic-2.0"):
            self.modern_install(repository, **kwargs)
        else:
            self.legacy_install(repository, **kwargs)

    def python_version(self):
        output = self.execute(
            [self.python, "--version"], mix_stdout_and_stderr=True
        ).strip()
        match = re.match(r"Python (\d+\.\d+(\.\d+)?)", output)
        if not match:
            raise testing.InstanceError(
                "Unexpected `python --version` output: %r" % output
            )
        return match.group(1)

    def legacy_install(
        self,
        repository,
        override_arguments={},
        other_cwd=False,
        quick=False,
        interactive=False,
    ):
        testing.logger.debug("Installing legacy Critic ...")

        self.legacy_installing = True

        try:
            version = self.python_version()
            if not version.startswith("2.7."):
                raise testing.InstanceError(
                    "Invalid Python version for legacy install: %s" % version
                )
        except GuestCommandError:
            if self.install_python is not None:
                raise testing.InstanceError(
                    "Python executable not found: " + self.install_python
                )

            testing.logger.debug("Installing Python 2.7 ...")

            self.apt_install("python2.7")

            testing.logger.info("Installed Python 2.7: %s", self.python_version())

        if not interactive:
            use_arguments = {
                "--headless": True,
                "--system-hostname": self.hostname,
                "--auth-mode": "critic",
                "--session-type": "cookie",
                "--admin-username": "admin",
                "--admin-email": "admin@example.org",
                "--admin-fullname": "'Testing Administrator'",
                "--admin-password": "testing",
                "--smtp-host": self.vboxhost,
                "--smtp-port": str(self.mailbox.port),
                "--smtp-no-ssl-tls": True,
                "--skip-testmail-check": True,
            }

            if self.mailbox.credentials:
                use_arguments["--smtp-username"] = self.mailbox.credentials["username"]
                use_arguments["--smtp-password"] = self.mailbox.credentials["password"]

            if self.coverage:
                use_arguments["--coverage-dir"] = COVERAGE_DIR

            if self.has_flag("system-recipients"):
                use_arguments["--system-recipient"] = "system@example.org"
        else:
            use_arguments = {"--admin-password": "testing"}

        if self.has_flag("minimum-password-hash-time"):
            use_arguments["--minimum-password-hash-time"] = "0.01"

        if self.has_flag("is-testing"):
            use_arguments["--is-testing"] = True

        if self.has_flag("web-server-integration") and self.arguments.vm_web_server:
            use_arguments["--web-server-integration"] = self.arguments.vm_web_server

        for name, value in override_arguments.items():
            if value is None:
                if name in use_arguments:
                    del use_arguments[name]
            else:
                use_arguments[name] = value

        arguments = []

        for name, value in use_arguments.items():
            arguments.append(name)
            if value is not True:
                arguments.append(value)

        if self.upgrade_commit:
            output = subprocess.check_output(
                [
                    "git",
                    "log",
                    "--oneline",
                    self.install_commit,
                    "--",
                    "background/servicemanager.py",
                ]
            ).decode()

            for line in output.splitlines():
                sha1, subject = line.split(" ", 1)
                if subject == "Make sure background services run with correct $HOME":
                    self.restrict_access()
                    break
        else:
            self.restrict_access()

        if other_cwd and self.has_flag("pwd-independence"):
            install_py = "critic/install.py"
            cwd = None
        else:
            install_py = "install.py"
            cwd = "critic"

        self.execute(
            ["sudo", self.python, "-u", install_py] + arguments,
            cwd=cwd,
            interactive="--headless" not in use_arguments,
        )

        self.legacy_installed = True
        self.criticctl_path = "/usr/bin/criticctl"

        if not quick:
            try:
                testmail = self.mailbox.pop(
                    testing.mailbox.WithSubject("Test email from Critic")
                )

                if not testmail:
                    testing.expect.check("<test email>", "<no test email received>")
                else:
                    testing.expect.check("admin@example.org", testmail.header("To"))
                    testing.expect.check(
                        "This is the configuration test email from Critic.",
                        "\n".join(testmail.lines),
                    )

                self.mailbox.check_empty()
                self.check_service_logs()
            except testing.TestFailure as error:
                if error.message:
                    testing.logger.error("Basic test: %s" % error.message)

                # If basic tests fail, there's no reason to further test this
                # instance; it seems to be properly broken.
                raise testing.InstanceError

            if self.arguments.mirror_upgrade_host:
                self.mirror_upgrade()
            else:
                # Add "developer" role to get stacktraces in error messages.
                self.execute(
                    [
                        "sudo",
                        "criticctl",
                        "addrole",
                        "--name",
                        "admin",
                        "--role",
                        "developer",
                    ]
                )

                # Add some regular users.
                for name in ("alice", "bob", "dave", "erin"):
                    self.adduser(name)

                self.adduser("howard")
                self.execute(
                    [
                        "sudo",
                        "criticctl",
                        "addrole",
                        "--name",
                        "howard",
                        "--role",
                        "newswriter",
                    ]
                )

        self.current_commit = self.install_commit

        if not quick and not self.arguments.mirror_upgrade_host:
            try:
                self.frontend.run_basic_tests()
                self.mailbox.check_empty()
            except testing.TestFailure as error:
                if error.message:
                    testing.logger.error("Basic test: %s" % error.message)

                # If basic tests fail, there's no reason to further test this
                # instance; it seems to be properly broken.
                raise testing.InstanceError

        testing.logger.info("Installed Critic: %s" % self.install_commit_description)

        self.__installed = True

    def pip_install(self, *packages):
        self.execute(
            [
                "sudo",
                "-H",
                "/var/lib/critic/bin/pip",
                "install",
                "-i",
                "http://host:3141/root/pypi/",
                "--trusted-host",
                "host",
                "--upgrade",
            ]
            + list(packages)
        )

    def setup_virtual_environment(self, *, is_upgrade=False):
        try:
            self.execute(["file", "-E", "/var/lib/critic/pyvenv.cfg"])
        except GuestCommandError:
            try:
                self.execute([self.python, "-m", "ensurepip", "--version"])
            except GuestCommandError:
                testing.logger.debug("Installing virtualenv support ...")
                self.apt_install("python3-venv")

            self.execute(["sudo", "-H", self.python, "-m", "venv", "/var/lib/critic"])

        self.pip_install("pip", "wheel")
        self.pip_install("critic/")

        self.legacy_installed = False
        self.criticctl_path = "/var/lib/critic/bin/criticctl"

    def modern_install(self, repository, *, quick=False):
        testing.logger.debug("Installing modern Critic ...")

        self.restrict_access()
        self.setup_virtual_environment(is_upgrade=False)

        self.criticctl(["run-task", "install", "--install-postgresql"])
        self.criticctl(["run-task", "install:systemd-service"])

        # Configure application container.
        if self.arguments.vm_web_server in ("nginx+uwsgi", "uwsgi"):
            self.criticctl(
                ["run-task", "container:uwsgi", "--install-uwsgi", "--enable-app"]
            )
        elif self.arguments.vm_web_server == "nginx+aiohttp":
            self.criticctl(["run-task", "container:aiohttp", "--unix"])
        else:
            raise testing.TestFailure("Unsupported VM web server integration!")

        # Configure HTTP front-end.
        if self.arguments.vm_web_server in ("nginx+uwsgi", "nginx+aiohttp"):
            self.criticctl(
                [
                    "run-task",
                    "frontend:nginx",
                    "--install-nginx",
                    "--access-scheme=http",
                    "--enable-site",
                    "--disable-default-site",
                ]
            )
        elif self.arguments.vm_web_server == "uwsgi":
            self.criticctl(
                ["run-task", "frontend:uwsgi", "--access-scheme=http", "--enable-app"]
            )
        else:
            raise testing.TestFailure("Unsupported VM web server integration!")

        self.criticctl(["run-task", "calibrate-pwhash", "--hash-time", "0.01"])

        def setting(name, value):
            return "'%s:%s'" % (name, json.dumps(value))

        settings = [
            setting("system.recipients", ["system@example.org"]),
            setting("system.is_testing", True),
            setting("smtp.configured", True),
            setting("smtp.host", self.vboxhost),
            setting("smtp.port", self.mailbox.port),
        ]
        if self.arguments.debug:
            settings.append(setting("system.is_debugging", True))
        if self.mailbox.credentials:
            settings.append(
                setting(
                    "smtp.credentials",
                    {
                        "username": self.mailbox.credentials["username"],
                        "password": self.mailbox.credentials["password"],
                    },
                )
            )
        self.criticctl(["settings", "set"] + settings)
        self.execute(["sudo", "systemctl", "start", "critic-main-system.service"])
        if self.arguments.vm_web_server == "nginx+aiohttp":
            self.execute(
                ["sudo", "systemctl", "start", "critic-main-container.service"]
            )

        self.adduser(
            "admin",
            fullname="Testing Administrator",
            roles=["administrator", "repositories", "newswriter", "developer"],
        )

        if not quick:
            try:
                self.mailbox.check_empty()
                self.check_service_logs()
            except testing.TestFailure as error:
                if error.args:
                    testing.logger.error("Basic test: %s" % error)

                # If basic tests fail, there's no reason to further test this
                # instance; it seems to be properly broken.
                raise testing.InstanceError

            if self.arguments.mirror_upgrade_host:
                self.mirror_upgrade()
            else:
                # Add some regular users.
                for name in ("alice", "bob", "dave", "erin"):
                    self.adduser(name)
                self.adduser("howard", roles=["newswriter"])

        self.current_commit = self.install_commit

        if not quick and not self.arguments.mirror_upgrade_host:
            try:
                self.frontend.run_basic_tests()
                self.mailbox.check_empty()
            except testing.TestFailure as error:
                if error.args:
                    testing.logger.error("Basic test: %s" % error)

                # If basic tests fail, there's no reason to further test this
                # instance; it seems to be properly broken.
                raise testing.InstanceError

        testing.logger.info("Installed Critic: %s", self.install_commit_description)

        self.__installed = True

    def check_upgrade(self):
        if not self.upgrade_commit:
            raise testing.NotSupported("--upgrade-from argument not given")

    def upgrade(
        self,
        override_arguments={},
        other_cwd=False,
        quick=False,
        interactive=False,
        is_after_test=False,
    ):
        if not self.upgrade_commit:
            return
        if self.upgrade_commit == self.current_commit:
            return
        if self.arguments.upgrade_after and not is_after_test:
            return

        testing.logger.debug("Upgrading Critic ...")

        self.restrict_access()

        self.execute(["git", "checkout", self.upgrade_commit], cwd="critic")
        self.execute(["git", "submodule", "update", "--recursive"], cwd="critic")

        # Setting this will make has_flag() from now on (including when used
        # in the rest of this function) check the upgraded-to commit rather
        # than the initially installed commit.
        self.__upgraded = True

        was_legacy_installed = self.legacy_installed

        self.setup_virtual_environment(is_upgrade=True)

        self.criticctl(["run-task", "upgrade", "--dump-database"])

        if self.arguments.debug:
            self.criticctl(["settings", "set", "system.is_debugging:true"])

        self.current_commit = self.upgrade_commit

        if was_legacy_installed:
            self.criticctl(["run-task", "install:systemd-service", "--start-service"])
            self.criticctl(
                [
                    "run-task",
                    "container:uwsgi",
                    "--install-uwsgi",
                    "--force",
                    "--enable-app",
                ]
            )
            self.criticctl(["run-task", "frontend:uwsgi", "--force", "--enable-app"])

        if not quick and not self.arguments.mirror_upgrade_host:
            self.frontend.run_basic_tests()

        testing.logger.info("Upgraded Critic: %s" % self.upgrade_commit_description)

    def check_extend(self, repository, pre_upgrade=False):
        commit = self.install_commit if pre_upgrade else self.tested_commit
        if not testing.exists_at(commit, "extend.py"):
            raise testing.NotSupported("tested commit lacks extend.py")
        if not self.arguments.test_extensions:
            raise testing.NotSupported("--test-extensions argument not given")
        if not repository.v8_jsshell_path:
            raise testing.NotSupported("v8-jsshell sub-module not initialized")

    def extend(self, repository):
        self.check_extend(repository)

        testing.logger.debug("Extending Critic ...")

        def internal(action, extra_argv=None):
            argv = [
                "sudo",
                self.python,
                "-u",
                "extend.py",
                "--headless",
                "--%s" % action,
            ]

            if extra_argv:
                argv.extend(extra_argv)

            self.execute(argv, cwd="critic")

        internal("prereqs", ["--libcurl-flavor=gnutls"])

        submodule_path = "installation/externals/v8-jsshell"

        v8_jsshell_sha1 = testing.repository.submodule_sha1(
            os.getcwd(), self.current_commit, submodule_path
        )
        cached_executable = os.path.join(
            self.arguments.cache_dir,
            self.identifier,
            "v8-jsshell",
            v8_jsshell_sha1 + "-gnutls",
        )

        if (
            self.upgrade_commit is not None
            and self.install_commit == self.current_commit
            and self.upgrade_commit != self.current_commit
        ):
            # We're extending before upgrading.  Don't use a cached executable
            # now if the upgrade changes the sub-module reference, since this
            # breaks upgrade.py's automatic invocation of extend.py.

            upgraded_v8_jsshell_sha1 = testing.repository.submodule_sha1(
                os.getcwd(), self.upgrade_commit, submodule_path
            )
            if upgraded_v8_jsshell_sha1 != v8_jsshell_sha1:
                testing.logger.debug("Caching of v8-jsshell disabled")
                cached_executable = None

        if cached_executable and os.path.isfile(cached_executable):
            self.execute(
                ["mkdir", "installation/externals/v8-jsshell/out"], cwd="critic"
            )
            self.copyto(
                cached_executable,
                "critic/installation/externals/v8-jsshell/out/jsshell",
            )
            testing.logger.debug("Copied cached v8-jsshell executable to instance")
        else:
            if repository.v8_url:
                extra_argv = ["--with-v8=%s" % repository.v8_url]
            else:
                extra_argv = None

            internal("fetch", extra_argv)

            # v8_sha1 = subprocess.check_output(
            #     ["git", "ls-tree", "HEAD", "v8"],
            #     cwd="installation/externals/v8-jsshell").split()[2]
            # cached_v8deps = os.path.join(self.arguments.cache_dir,
            #                              "v8-dependencies",
            #                              "%s.tar.bz2" % v8_sha1)
            # if os.path.isfile(cached_v8deps):
            #     self.copyto(cached_v8deps, "v8deps.tar.bz2")
            #     internal("import-v8-dependencies=~/v8deps.tar.bz2")
            # else:
            #     internal("export-v8-dependencies=~/v8deps.tar.bz2")
            #     if not os.path.isdir(os.path.dirname(cached_v8deps)):
            #         os.makedirs(os.path.dirname(cached_v8deps))
            #     self.copyfrom("v8deps.tar.bz2", cached_v8deps)

            internal("build")

            if cached_executable:
                if not os.path.isdir(os.path.dirname(cached_executable)):
                    os.makedirs(os.path.dirname(cached_executable))
                self.copyfrom(
                    "critic/installation/externals/v8-jsshell/out/jsshell",
                    cached_executable,
                )
                testing.logger.debug("Copied built v8-jsshell executable from instance")

        internal("install")
        internal("enable")

        self.frontend.run_basic_tests()

        testing.logger.info("Extensions enabled")

    def restart(self):
        self.execute(["sudo", "criticctl", "restart"])

    def uninstall(self):
        self.execute(
            ["sudo", self.python, "uninstall.py", "--headless", "--keep-going"],
            cwd="critic",
        )

        # Delete the regular users.
        for name in ("alice", "bob", "dave", "erin"):
            self.execute(["sudo", "deluser", "--remove-home", name])

        self.execute(["sudo", "deluser", "--remove-home", "howard"])

        self.__installed = False
        self.__upgraded = False

    def finish(self):
        if not self.__started:
            return

        # if self.__installed:
        #     self.criticctl(["stop"])

        if self.coverage:
            sys.stdout.write(
                self.execute(
                    [
                        "sudo",
                        self.python,
                        "coverage.py",
                        "--coverage-dir",
                        COVERAGE_DIR,
                        "--critic-dir",
                        "/etc/critic/main",
                        "--critic-dir",
                        "/usr/share/critic",
                    ],
                    cwd="/usr/share/critic",
                )
            )

        # Check that we didn't leave any files owned by root anywhere in the
        # directory we installed from.
        self.execute(["chmod", "-R", "a+r", "critic"])
        self.execute(["rm", "-r", "critic"])

    def run_unittest(self, args):
        args = ["'%s'" % arg for arg in args]
        if self.coverage:
            args = ["--coverage"] + args
        return self.execute(
            [
                "cd",
                "/usr/share/critic",
                "&&",
                "sudo",
                "-H",
                "-u",
                "critic",
                "PYTHONPATH=/etc/critic/main:/usr/share/critic",
                "/var/lib/critic/venv/bin/python",
                "-u",
                "-m",
                "run_unittest",
            ]
            + args,
            log_stderr=False,
        )

    def gc(self, repository):
        self.execute(
            ["git", "gc", "--prune=now"],
            cwd=os.path.join("/var/git", repository),
            as_user="alice",
        )

    def filter_service_logs(self, level, service_names):
        helper = "testing/input/service_log_filter.py"
        if not (self.__upgraded or testing.exists_at(self.install_commit, helper)):
            # We're upgrading from a commit where the helper for filtering
            # service logs isn't supported, and haven't upgraded yet.
            return
        logfile_paths = {
            os.path.join("/var/log/critic/main", service_name + ".log"): service_name
            for service_name in service_names
        }
        data = json.loads(
            self.execute(
                ["sudo", self.python, "critic/" + helper, level]
                + list(logfile_paths.keys()),
                log_stdout=False,
            )
        )
        return {
            logfile_paths[logfile_path]: entries
            for logfile_path, entries in data.items()
        }

    def mirror_upgrade(self):
        import requests

        # Need to add self to the `critic` group in order to push to the
        # repositories under /var/git/.
        self.execute(["sudo", "addgroup", "$USER", "critic"])

        result = requests.get(
            os.path.join(self.arguments.mirror_upgrade_host, "api/v1/repositories")
        ).json()

        mirror_dir = self.arguments.mirror_cache_dir or tempfile.mkdtemp()

        for repository in result["repositories"]:
            path = repository["path"]

            self.execute(
                [
                    "sudo",
                    "-H",
                    "-u",
                    "critic",
                    "git",
                    "init",
                    "--bare",
                    "--shared",
                    path,
                ]
            )

            mirror_path = os.path.join(mirror_dir, repository["relative_path"])
            if os.path.isdir(mirror_path):
                testing.execute.execute(["git", "fetch", "--all"], cwd=mirror_path)
            else:
                testing.execute.execute(
                    ["git", "clone", "--mirror", repository["url"], mirror_path]
                )

            testing.execute.execute(
                ["git", "push", f"{self.hostname}:{path}", "refs/*:refs/*"],
                cwd=mirror_path,
            )

        self.copyto(self.arguments.mirror_upgrade_dbdump, "/tmp/dbdump")

        try:
            self.execute(
                [
                    "sudo",
                    "-H",
                    "-u",
                    "critic",
                    "pg_restore",
                    "-c",
                    "-d",
                    "critic",
                    "/tmp/dbdump",
                ]
            )
        except GuestCommandError:
            # Typically, a variety of errors and warnings will be output, and
            # the command "fails". Probably, all the relevant data will have
            # been imported, though.
            pass

        self.execute(
            ["sudo", "-H", "-u", "critic", "psql"],
            stdin_data="UPDATE trackedbranches SET disabled=TRUE;",
        )

    def install_customization(self):
        self.pip_install("critic/testing/input/critic-customization")

    def synchronize_service(self, *service_names, force_maintenance=False, timeout=30):
        if not self.legacy_installed:
            super().synchronize_service(
                *service_names, force_maintenance=force_maintenance, timeout=timeout
            )
            return

        # This is the "legacy" mechanism for synchronizing background
        # services. We need to use it temporarily when a legacy commit has been
        # installed, before we upgrade to a modern commit.
        for service_name in service_names:
            self.legacy_synchronize_service(service_name, force_maintenance, timeout)

    def legacy_synchronize_service(self, service_name, force_maintenance, timeout):
        helper = "testing/input/service_synchronization_helper.py"
        if not (self.__upgraded or testing.exists_at(self.install_commit, helper)):
            # We're upgrading from a commit where background services don't
            # support synchronization, and haven't upgraded yet.  Sleep a (long)
            # while and pray that the service is idle when we wake up.
            testing.logger.debug(
                "Synchronizing service: %s (sleeping %d seconds)"
                % (service_name, timeout)
            )
            time.sleep(timeout)
            return
        testing.logger.debug("Synchronizing service: %s" % service_name)
        pidfile_path = os.path.join("/var/run/critic/main", service_name + ".pid")
        if force_maintenance:
            signum = int(signal.SIGUSR2)
        else:
            signum = int(signal.SIGUSR1)
        before = time.time()
        self.execute(
            [
                "sudo",
                "python",
                "critic/" + helper,
                pidfile_path,
                str(signum),
                str(timeout),
            ]
        )
        after = time.time()
        testing.logger.debug(
            "Synchronized service: %s in %.2f seconds" % (service_name, after - before)
        )

    @property
    def running_services(self):
        common_services = [
            "branchtracker",
            "branchupdater",
            "githook",
            "maildelivery",
            "maintenance",
            "reviewupdater",
            "servicemanager",
        ]
        if self.legacy_installed:
            return common_services + ["highlight", "changeset"]
        return common_services + ["differenceengine"]


def setup(subparsers):
    parser = subparsers.add_parser(
        "virtualbox",
        description="Test against Critic installed in a VirtualBox VM.",
        help=(
            "This flavor of testing can run all tests, but requires a lot of "
            "configuration and preparation. It mainly complements the "
            '`Docker` flavor by being a classic "monolithic" install.'
        ),
    )
    parser.add_argument(
        "--host-alias",
        dest="runner_hostname",
        default="host",
        help="Name that resolves to the host machine in the VM [default=host]",
    )
    parser.add_argument(
        "--instance", help="VirtualBox instance to test in (name or UUID)"
    )
    parser.add_argument(
        "--hostname",
        dest="critic_hostname",
        help="VirtualBox instance hostname [default=VM_INSTANCE",
    )
    parser.add_argument(
        "--snapshot",
        default="clean",
        help="VirtualBox snapshot (name or UUID) to restore [default=clean]",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        help="VirtualBox instance SSH port [default=22]",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=80,
        help="VirtualBox instance HTTP port [default=80]",
    )
    parser.add_argument(
        "--web-server",
        choices=("apache+aiohttp", "nginx+aiohttp", "nginx+uwsgi", "uwsgi"),
        help="Web server to tell Critic to install and configure",
    )
    parser.add_argument(
        "--install-python", help="Python executable to use in VM when installing"
    )
    parser.add_argument(
        "--upgrade-python", help="Python executable to use in VM when upgrading"
    )
    parser.set_defaults(flavor="virtualbox")
