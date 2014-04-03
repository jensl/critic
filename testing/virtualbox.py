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
import subprocess
import time
import fcntl
import select
import errno
import datetime
import signal
import json

import testing

# Directory (on guest system) to store coverage data in.
COVERAGE_DIR = "/var/tmp/critic/coverage"

def setnonblocking(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

class HostCommandError(testing.InstanceError):
    def __init__(self, command, output):
        super(HostCommandError, self).__init__(
            "HostCommandError: %s\nOutput:\n%s" % (command, output))
        self.command = command
        self.output = output

class GuestCommandError(testing.InstanceError):
    def __init__(self, command, stdout, stderr=None):
        super(GuestCommandError, self).__init__(
            "GuestCommandError: %s\nOutput:\n%s" % (command, stderr or stdout))
        self.command = command
        self.stdout = stdout
        self.stderr = stderr

class Instance(testing.Instance):
    def __init__(self, arguments, install_commit=None, upgrade_commit=None,
                 frontend=None):
        self.arguments = arguments
        self.vboxhost = getattr(arguments, "vbox_host", "host")
        self.identifier = arguments.vm_identifier
        self.snapshot = arguments.vm_snapshot
        self.hostname = arguments.vm_hostname or self.identifier
        self.ssh_port = arguments.vm_ssh_port
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

        # Check that the identified VM actually exists:
        output = subprocess.check_output(
            ["VBoxManage", "list", "vms"],
            stderr=subprocess.STDOUT)
        if not self.__isincluded(output):
            raise testing.Error("Invalid VM identifier: %s" % self.identifier)

        # Check that the identified snapshot actually exists (and that there
        # aren't multiple snapshots with the same name):
        count = self.count_snapshots(self.snapshot)
        if count == 0:
            raise testing.Error("Invalid VM snapshot: %s (not found)"
                                % self.snapshot)
        elif count > 1:
            raise testing.Error("Invalid VM snapshot: %s (matches multiple snapshots)"
                                % self.snapshot)

        # Check that the VM isn't running:
        state = self.state()
        if state != "poweroff":
            raise testing.Error("Invalid VM state: %s (expected 'poweroff')"
                                % state)

        self.__reset()

    def __reset(self):
        self.__started = False
        self.__installed = False
        self.__upgraded = False
        self.__users = ["admin"]
        self.__user_ids = { "admin": 1 }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.__started:
            self.stop()
        self.__reset()
        return False

    def __vmcommand(self, command, *arguments):
        argv = ["VBoxManage", command, self.identifier] + list(arguments)
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(argv, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            raise HostCommandError(" ".join(argv), error.output)

    def __isincluded(self, output):
        name = '"%s"' % self.identifier
        uuid = '{%s}' % self.identifier

        for line in output.splitlines():
            if name in line or uuid in line:
                return True
        else:
            return False

    def isrunning(self):
        output = subprocess.check_output(
            ["VBoxManage", "list", "runningvms"],
            stderr=subprocess.STDOUT)
        return self.__isincluded(output)

    def state(self):
        output = self.__vmcommand("showvminfo", "--machinereadable")
        for line in output.splitlines():
            if line.startswith("VMState="):
                return eval(line[len("VMState="):])
        return "<not found>"

    def count_snapshots(self, identifier):
        try:
            output = subprocess.check_output(
                ["VBoxManage", "snapshot", self.identifier, "list"],
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # Assuming we've already checked that 'self.identifier' is a valid
            # VM identifier, the most likely cause of this failure is that the
            # VM has no snapshots.
            return 0
        else:
            name = "Name: %s (" % identifier
            uuid = "(UUID: %s)" % identifier
            count = 0
            for line in output.splitlines():
                if name in line or uuid in line:
                    count += 1
            return count

    def wait(self):
        testing.logger.debug("Waiting for VM to come online ...")

        while True:
            try:
                self.execute(["true"], timeout=1)
            except GuestCommandError:
                time.sleep(0.5)
            else:
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
        index = 1

        while True:
            temporary_name = "%s-%d" % (name, index)
            if self.count_snapshots(temporary_name) == 0:
                break
            index += 1

        self.__vmcommand("snapshot", "take", temporary_name, "--pause")
        self.__vmcommand("snapshot", "delete", name)
        self.__vmcommand("snapshot", "edit", temporary_name, "--name", name)

    def execute(self, argv, cwd=None, timeout=None, interactive=False,
                as_user=None, log_stdout=True, log_stderr=True):
        guest_argv = list(argv)
        if cwd is not None:
            guest_argv[:0] = ["cd", cwd, "&&"]
        host_argv = ["ssh"]
        if self.ssh_port != 22:
            host_argv.extend(["-p", str(self.ssh_port)])
        if timeout is not None:
            host_argv.extend(["-o", "ConnectTimeout=%d" % timeout])
        if not interactive:
            host_argv.append("-n")
        if as_user is not None:
            host_argv.extend(["-l", as_user])
        host_argv.append(self.hostname)

        testing.logger.debug("Running: " + " ".join(host_argv + guest_argv))

        process = subprocess.Popen(
            host_argv + guest_argv,
            stdout=subprocess.PIPE if not interactive else None,
            stderr=subprocess.PIPE if not interactive else None)

        class BufferedLineReader(object):
            def __init__(self, source):
                self.source = source
                self.buffer = ""

            def readline(self):
                try:
                    while self.source is not None:
                        try:
                            line, self.buffer = self.buffer.split("\n", 1)
                        except ValueError:
                            pass
                        else:
                            return line + "\n"
                        data = self.source.read(1024)
                        if not data:
                            self.source = None
                            break
                        self.buffer += data
                    line = self.buffer
                    self.buffer = ""
                    return line
                except IOError as error:
                    if error.errno == errno.EAGAIN:
                        return None
                    raise

        stdout_data = ""
        stdout_reader = BufferedLineReader(process.stdout)

        stderr_data = ""
        stderr_reader = BufferedLineReader(process.stderr)

        if not interactive:
            setnonblocking(process.stdout)
            setnonblocking(process.stderr)

            poll = select.poll()
            poll.register(process.stdout)
            poll.register(process.stderr)

            stdout_done = False
            stderr_done = False

            while not (stdout_done and stderr_done):
                poll.poll()

                while not stdout_done:
                    line = stdout_reader.readline()
                    if line is None:
                        break
                    elif not line:
                        poll.unregister(process.stdout)
                        stdout_done = True
                        break
                    else:
                        stdout_data += line
                        if log_stdout:
                            testing.logger.log(testing.STDOUT, line.rstrip("\n"))

                while not stderr_done:
                    line = stderr_reader.readline()
                    if line is None:
                        break
                    elif not line:
                        poll.unregister(process.stderr)
                        stderr_done = True
                        break
                    else:
                        stderr_data += line
                        if log_stderr:
                            testing.logger.log(testing.STDERR, line.rstrip("\n"))

        process.wait()

        if process.returncode != 0:
            raise GuestCommandError(" ".join(argv), stdout_data, stderr_data)

        return stdout_data

    def copyto(self, source, target, as_user=None):
        target = "%s:%s" % (self.hostname, target)
        if as_user:
            target = "%s@%s" % (as_user, target)
        argv = ["scp", "-q", "-P", str(self.ssh_port), source, target]
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(argv, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            raise GuestCommandError(" ".join(argv), error.output)

    def copyfrom(self, source, target, as_user=None):
        source = "%s:%s" % (self.hostname, source)
        if as_user:
            source = "%s@%s" % (as_user, source)
        argv = ["scp", "-q", "-P", str(self.ssh_port), source, target]
        try:
            testing.logger.debug("Running: " + " ".join(argv))
            return subprocess.check_output(argv, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            raise GuestCommandError(" ".join(argv), error.output)

    def adduser(self, name, email=None, fullname=None, password=None):
        if email is None:
            email = "%s@example.org" % name
        if fullname is None:
            fullname = "%s von Testing" % name.capitalize()
        if password is None:
            password = "testing"

        self.execute([
            "sudo", "criticctl", "adduser", "--name", name, "--email", email,
            "--fullname", "'%s'" % fullname, "--password", password,
            "&&",
            "sudo", "adduser", "--ingroup", "critic", "--disabled-password",
            "--gecos", "''", name])

        # Running all commands with a single self.execute() call is just an
        # optimization; SSH sessions are fairly expensive to start.
        self.execute([
            "sudo", "mkdir", ".ssh",
            "&&",
            "sudo", "cp", "$HOME/.ssh/authorized_keys", ".ssh/",
            "&&",
            "sudo", "chown", "-R", name, ".ssh/",
            "&&",
            "sudo", "-H", "-u", name, "git", "config", "--global", "user.name",
            "'%s'" % fullname,
            "&&",
            "sudo", "-H", "-u", name, "git", "config", "--global", "user.email",
            email],
                     cwd="/home/%s" % name)

        self.__users.append(name)
        self.__user_ids[name] = len(self.__users)

    def userid(self, name):
        return self.__user_ids.get(name)

    def has_flag(self, flag):
        if self.upgrade_commit and self.__upgraded:
            check_commit = self.upgrade_commit
        else:
            check_commit = self.install_commit
        return testing.has_flag(check_commit, flag)

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

    def install(self, repository, override_arguments={}, other_cwd=False,
                quick=False, interactive=False):
        testing.logger.debug("Installing Critic ...")

        if not interactive:
            use_arguments = { "--headless": True,
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
                              "--skip-testmail-check": True }

            if self.mailbox.credentials:
                use_arguments["--smtp-username"] = self.mailbox.credentials["username"]
                use_arguments["--smtp-password"] = self.mailbox.credentials["password"]

            if self.coverage:
                use_arguments["--coverage-dir"] = COVERAGE_DIR

            if self.has_flag("system-recipients"):
                use_arguments["--system-recipient"] = "system@example.org"
        else:
            use_arguments = { "--admin-password": "testing" }

        if self.has_flag("minimum-password-hash-time"):
            use_arguments["--minimum-password-hash-time"] = "0.01"

        if self.has_flag("is-testing"):
            use_arguments["--is-testing"] = True

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

        # First install (if necessary) Git.
        try:
            self.execute(["git", "--version"])
        except GuestCommandError:
            testing.logger.debug("Installing Git ...")

            self.execute(["sudo", "DEBIAN_FRONTEND=noninteractive",
                          "apt-get", "-qq", "update"])

            self.execute(["sudo", "DEBIAN_FRONTEND=noninteractive",
                          "apt-get", "-qq", "-y", "install", "git-core"])

            testing.logger.info("Installed Git: %s" % self.execute(["git", "--version"]).strip())

        self.execute(["git", "clone", repository.url, "critic"])
        self.execute(["git", "fetch", "--quiet", "&&",
                      "git", "checkout", "--quiet", self.install_commit],
                     cwd="critic")

        if self.upgrade_commit:
            output = subprocess.check_output(
                ["git", "log", "--oneline", self.install_commit, "--",
                 "background/servicemanager.py"])

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
            ["sudo", "python", "-u", install_py] + arguments,
            cwd=cwd, interactive="--headless" not in use_arguments)

        if not quick:
            try:
                testmail = self.mailbox.pop(
                    testing.mailbox.WithSubject("Test email from Critic"))

                if not testmail:
                    testing.expect.check("<test email>", "<no test email received>")
                else:
                    testing.expect.check("admin@example.org",
                                         testmail.header("To"))
                    testing.expect.check("This is the configuration test email from Critic.",
                                         "\n".join(testmail.lines))

                self.mailbox.check_empty()
                self.check_service_logs()
            except testing.TestFailure as error:
                if error.message:
                    testing.logger.error("Basic test: %s" % error.message)

                # If basic tests fail, there's no reason to further test this
                # instance; it seems to be properly broken.
                raise testing.InstanceError

            # Add "developer" role to get stacktraces in error messages.
            self.execute(["sudo", "criticctl", "addrole",
                          "--name", "admin",
                          "--role", "developer"])

            # Add some regular users.
            for name in ("alice", "bob", "dave", "erin"):
                self.adduser(name)

            self.adduser("howard")
            self.execute(["sudo", "criticctl", "addrole",
                          "--name", "howard",
                          "--role", "newswriter"])

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
        self.current_commit = self.install_commit

    def check_upgrade(self):
        if not self.upgrade_commit:
            raise testing.NotSupported("--upgrade-from argument not given")

    def check_late_upgrade(self):
        # First of all: late upgrade testing is only meaningful if we're
        # upgrading at all.
        self.check_upgrade()

        changed_files = subprocess.check_output(
            ["git", "diff", "--name-only",
             "%s..%s" % (self.install_commit, self.upgrade_commit),
             "--", "installation/migrations/"]).splitlines()

        if not changed_files:
            raise testing.NotSupported("no migration scripts added or modified")

        # This commit added testing/tests/002-late-upgrade/.  It's actually a
        # rather arbitrary point in the history to limit at, but it works, and
        # some really old commits don't.
        FIRST_LATE_UPGRADE = "80512c5a80b29d269fb6f955e1f757920e63d211"

        try:
            subprocess.check_call(
                ["git", "merge-base", "--is-ancestor",
                 FIRST_LATE_UPGRADE, self.install_commit])
        except subprocess.CalledProcessError:
            raise testing.NotSupported(
                "installed commit predates late upgrade testing")

    def upgrade(self, override_arguments={}, other_cwd=False, quick=False,
                interactive=False):
        if self.upgrade_commit:
            testing.logger.debug("Upgrading Critic ...")

            self.restrict_access()

            if not interactive:
                use_arguments = { "--headless": True }
            else:
                use_arguments = {}

            if not self.has_flag("minimum-password-hash-time"):
                use_arguments["--minimum-password-hash-time"] = "0.01"

            if not self.has_flag("is-testing"):
                use_arguments["--is-testing"] = True

            if not self.has_flag("system-recipients"):
                use_arguments["--system-recipient"] = "system@example.org"

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

            self.execute(["git", "checkout", self.upgrade_commit], cwd="critic")
            self.execute(["git", "submodule", "update", "--recursive"], cwd="critic")

            # Setting this will make has_flag() from now on (including when used
            # in the rest of this function) check the upgraded-to commit rather
            # than the initially installed commit.
            self.__upgraded = True

            if other_cwd and self.has_flag("pwd-independence"):
                upgrade_py = "critic/upgrade.py"
                cwd = None
            else:
                upgrade_py = "upgrade.py"
                cwd = "critic"

            self.execute(["sudo", "python", "-u", upgrade_py] + arguments,
                         cwd=cwd, interactive="--headless" not in use_arguments)

            if not quick:
                self.frontend.run_basic_tests()

            testing.logger.info("Upgraded Critic: %s" % self.upgrade_commit_description)

            self.current_commit = self.upgrade_commit

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
            argv = ["sudo", "python", "-u", "extend.py", "--headless",
                    "--%s" % action]

            if extra_argv:
                argv.extend(extra_argv)

            self.execute(argv, cwd="critic")

        internal("prereqs")

        submodule_path = "installation/externals/v8-jsshell"

        v8_jsshell_sha1 = testing.repository.submodule_sha1(
            os.getcwd(), self.current_commit, submodule_path)
        cached_executable = os.path.join(self.arguments.cache_dir,
                                         self.identifier, "v8-jsshell",
                                         v8_jsshell_sha1)

        if os.path.isfile(cached_executable):
            self.execute(["mkdir", "installation/externals/v8-jsshell/out"], cwd="critic")
            self.copyto(cached_executable,
                        "critic/installation/externals/v8-jsshell/out/jsshell")
            testing.logger.debug("Copied cached v8-jsshell executable to instance")
        else:
            if repository.v8_url:
                extra_argv = ["--with-v8=%s" % repository.v8_url]
            else:
                extra_argv = None

            internal("fetch", extra_argv)

            v8_sha1 = subprocess.check_output(
                ["git", "ls-tree", "HEAD", "v8"],
                cwd="installation/externals/v8-jsshell").split()[2]
            cached_v8deps = os.path.join(self.arguments.cache_dir,
                                         "v8-dependencies",
                                         "%s.tar.bz2" % v8_sha1)
            if os.path.isfile(cached_v8deps):
                self.copyto(cached_v8deps, "v8deps.tar.bz2")
                internal("import-v8-dependencies=~/v8deps.tar.bz2")
            else:
                internal("export-v8-dependencies=~/v8deps.tar.bz2")
                if not os.path.isdir(os.path.dirname(cached_v8deps)):
                    os.makedirs(os.path.dirname(cached_v8deps))
                self.copyfrom("v8deps.tar.bz2", cached_v8deps)

            internal("build")
            if not os.path.isdir(os.path.dirname(cached_executable)):
                os.makedirs(os.path.dirname(cached_executable))
            self.copyfrom("critic/installation/externals/v8-jsshell/out/jsshell",
                          cached_executable)
            testing.logger.debug("Copied built v8-jsshell executable from instance")

        internal("install")
        internal("enable")

        self.frontend.run_basic_tests()

        testing.logger.info("Extensions enabled")

    def restart(self):
        self.execute(["sudo", "criticctl", "restart"])

    def uninstall(self):
        self.execute(
            ["sudo", "python", "uninstall.py", "--headless", "--keep-going"],
            cwd="critic")

        # Delete the regular users.
        for name in ("alice", "bob", "dave", "erin"):
            self.execute(["sudo", "deluser", "--remove-home", name])

        self.execute(["sudo", "deluser", "--remove-home", "howard"])

        self.__installed = False
        self.__upgraded = False

    def finish(self):
        if not self.__started:
            return

        if self.__installed:
            self.execute(["sudo", "service", "critic-main", "stop"])
            self.execute(["sudo", "service", "apache2", "stop"])

        if self.coverage:
            sys.stdout.write(self.execute(
                ["sudo", "python", "coverage.py",
                 "--coverage-dir", COVERAGE_DIR,
                 "--critic-dir", "/etc/critic/main",
                 "--critic-dir", "/usr/share/critic"],
                cwd="/usr/share/critic"))

        # Check that we didn't leave any files owned by root anywhere in the
        # directory we installed from.
        self.execute(["chmod", "-R", "a+r", "critic"])
        self.execute(["rm", "-r", "critic"])

    def unittest(self, module, tests, args=None):
        testing.logger.info("Running unit tests: %s (%s)"
                            % (module, ",".join(tests)))
        path = self.translateUnittestPath(module)
        if not args:
            args = []
        for test in tests:
            try:
                self.execute(["cd", "/usr/share/critic", "&&",
                              "sudo", "-H", "-u", "critic",
                              "PYTHONPATH=/etc/critic/main:/usr/share/critic",
                              "python", path, test] + args,
                             log_stderr=False)
            except GuestCommandError as error:
                output = "\n  ".join(error.stderr.splitlines())
                testing.logger.error("Unit tests failed: %s: %s\nOutput:\n  %s"
                                     % (module, test, output))

    def gc(self, repository):
        self.execute(["git", "gc", "--prune=now"],
                     cwd=os.path.join("/var/git", repository),
                     as_user="alice")

    def synchronize_service(self, service_name, force_maintenance=False, timeout=30):
        helper = "testing/input/service_synchronization_helper.py"
        if not (self.__upgraded or testing.exists_at(self.install_commit, helper)):
            # We're upgrading from a commit where background services don't
            # support synchronization, and haven't upgraded yet.  Sleep a (long)
            # while and pray that the service is idle when we wake up.
            testing.logger.debug("Synchronizing service: %s (sleeping %d seconds)"
                                 % (service_name, timeout))
            time.sleep(timeout)
            return
        testing.logger.debug("Synchronizing service: %s" % service_name)
        pidfile_path = os.path.join("/var/run/critic/main", service_name + ".pid")
        if force_maintenance:
            signum = signal.SIGUSR2
        else:
            signum = signal.SIGUSR1
        before = time.time()
        self.execute(
            ["sudo", "python", "critic/" + helper,
             pidfile_path, str(signum), str(timeout)])
        after = time.time()
        testing.logger.debug("Synchronized service: %s in %.2f seconds"
                             % (service_name, after - before))

    def filter_service_logs(self, level, service_names):
        helper = "testing/input/service_log_filter.py"
        if not (self.__upgraded or testing.exists_at(self.install_commit, helper)):
            # We're upgrading from a commit where the helper for filtering
            # service logs isn't supported, and haven't upgraded yet.
            return
        logfile_paths = {
            os.path.join("/var/log/critic/main", service_name + ".log"): service_name
            for service_name in service_names }
        try:
            data = json.loads(self.execute(
                ["sudo", "python", "critic/" + helper, level] + logfile_paths.keys(),
                log_stdout=False))
            return { logfile_paths[logfile_path]: entries
                     for logfile_path, entries in sorted(data.items()) }
        except GuestCommandError:
            return None
