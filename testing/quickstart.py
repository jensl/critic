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
import signal
import threading
import time
import json

import testing

class RepositoryURL(object):
    def __init__(self, path, name):
        self.path = path
        self.name = name

class Instance(testing.Instance):
    flags_off = ["full", "postgresql", "extensions", "upgrade", "uninstall"]

    install_commit = "HEAD"
    tested_commit = "HEAD"

    def __init__(self, frontend):
        super(Instance, self).__init__()
        self.frontend = frontend
        self.mailbox = None
        self.process = None
        self.hostname = "localhost"
        self.registeruser("admin")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.process:
            self.stop()
        return False

    @property
    def etc_dir(self):
        return os.path.join(self.state_dir, "etc")

    def start(self):
        pass

    def stop(self):
        testing.logger.debug("Stopping ...")

        self.process.send_signal(signal.SIGINT)
        self.process.wait()
        self.process = None

        testing.logger.debug("Stopped")

    def execute(self, *args, **kwargs):
        raise testing.NotSupported("quick-started instance doesn't support execute()")

    def criticctl(self, argv):
        for index, arg in enumerate(argv):
            if arg[0] == "'" == arg[-1]:
                argv[index] = arg[1:-1]

        argv = [os.path.join(self.state_dir, "bin", "criticctl")] + argv

        testing.logger.debug("Running: %s" % " ".join(argv))

        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        stdout, stderr = process.communicate()

        for line in stdout.splitlines():
            testing.logger.log(testing.STDOUT, line)
        for line in stderr.splitlines():
            testing.logger.log(testing.STDERR, line)

        if process.returncode == 0:
            return stdout
        else:
            raise testing.CriticctlError(" ".join(argv), stdout, stderr)

    def adduser(self, name, email=None, fullname=None, password=None):
        if email is None:
            email = "%s@example.org" % name
        if fullname is None:
            fullname = "%s von Testing" % name.capitalize()
        if password is None:
            password = "testing"

        self.criticctl(["adduser",
                        "--name", name,
                        "--email", email,
                        "--fullname", fullname,
                        "--password", password])

        self.registeruser(name)

    def has_flag(self, flag):
        return testing.has_flag("HEAD", flag)

    def repository_path(self, repository="critic"):
        return os.path.join(self.state_dir, "git/%s.git" % repository)

    def repository_url(self, name=None, repository="critic"):
        path = self.repository_path(repository)
        if name is None:
            return path
        return RepositoryURL(path, name)

    def install(self, repository, override_arguments={}, other_cwd=False,
                quick=False, interactive=False):
        argv = [sys.executable, "-u", "quickstart.py",
                "--testing",
                "--admin-username", "admin",
                "--admin-fullname", "Testing Administrator",
                "--admin-email", "admin@example.org",
                "--admin-password", "testing",
                "--system-recipient", "system@example.org",
                "--http-port", "0", # Use a random port.
                "--smtp-port", str(self.mailbox.port),
                "--smtp-username", self.mailbox.credentials["username"],
                "--smtp-password", self.mailbox.credentials["password"]]

        testing.logger.debug("Running: %s" % " ".join(argv))

        self.process = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def consume(stream, loglevel):
            try:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    testing.logger.log(loglevel, line.rstrip())
            except IOError:
                pass

        stderr_thread = threading.Thread(
            target=consume, args=(self.process.stderr, testing.STDERR))
        stderr_thread.daemon = True
        stderr_thread.start()

        line = self.process.stdout.readline().strip()
        key, _, value = line.partition("=")

        if key != "STATE":
            raise testing.InstanceError("Unexpected output: %r" % line)

        self.state_dir = value

        testing.logger.debug("State directory: %s" % value)

        line = self.process.stdout.readline().strip()
        key, _, value = line.partition("=")

        if key != "HTTP":
            raise testing.InstanceError("Unexpected output: %r" % line)

        hostname, _, port = value.partition(":")

        self.frontend.hostname = hostname
        self.frontend.http_port = int(port)

        testing.logger.debug("HTTP address: %s:%s" % (hostname, port))

        line = self.process.stdout.readline().strip()

        if line != "STARTED":
            raise testing.InstanceError("Unexpected output: %r" % line)

        # Add some regular users.
        for name in ("alice", "bob", "dave", "erin"):
            self.adduser(name)

        self.adduser("howard")
        self.criticctl(["addrole",
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

        testing.logger.info("Quick-started Critic in %s (%d)"
                            % (self.state_dir, self.frontend.http_port))

    def check_upgrade(self):
        raise testing.NotSupported("quick-started instance can't be upgraded")

    def upgrade(self, override_arguments={}, other_cwd=False, quick=False,
                interactive=False):
        pass

    def check_extend(self, repository, pre_upgrade=False):
        raise testing.NotSupported("quick-started instance doesn't support extensions")

    def extend(self, repository):
        self.check_extend(repository)

    def uninstall(self):
        raise testing.NotSupported("quick-started instance can't be uninstalled")

    def finish(self):
        pass

    def run_unittest(self, args):
        PYTHONPATH = ":".join([os.path.join(self.state_dir, "etc/main"),
                               os.path.join(os.getcwd(), "src"),
                               os.getcwd()])
        argv = [sys.executable, "-u", "-m", "run_unittest"] + args
        return self.executeProcess(argv, cwd="src", log_stderr=False,
                                   env={ "PYTHONPATH": PYTHONPATH })

    def gc(self, repository):
        self.executeProcess(
            ["git", "gc", "--prune=now"],
            cwd=os.path.join(self.state_dir, "git", repository))

    def synchronize_service(self, service_name, force_maintenance=False, timeout=30):
        helper = "testing/input/service_synchronization_helper.py"
        testing.logger.debug("Synchronizing service: %s" % service_name)
        pidfile_path = os.path.join(
            self.state_dir, "run/main", service_name + ".pid")
        if force_maintenance:
            signum = signal.SIGUSR2
        else:
            signum = signal.SIGUSR1
        before = time.time()
        try:
            self.executeProcess(
                ["python", helper, pidfile_path, str(signum), str(timeout)])
        except testing.CommandError:
            testing.logger.warning("Failed to synchronize service: %s"
                                   % service_name)
        else:
            after = time.time()
            testing.logger.debug("Synchronized service: %s in %.2f seconds"
                                 % (service_name, after - before))

    def filter_service_logs(self, level, service_names):
        helper = "testing/input/service_log_filter.py"
        logfile_paths = {
            os.path.join(
                self.state_dir, "log/main", service_name + ".log"): service_name
            for service_name in service_names }
        try:
            data = json.loads(self.executeProcess(
                ["python", helper, level] + logfile_paths.keys(),
                log_stdout=False))
            return { logfile_paths[logfile_path]: entries
                     for logfile_path, entries in sorted(data.items()) }
        except testing.CommandError:
            return None

    def restart(self):
        self.process.send_signal(signal.SIGUSR1)

        line = self.process.stdout.readline().strip()

        if line != "RESTARTED":
            raise testing.InstanceError("Unexpected output: %r" % line)
