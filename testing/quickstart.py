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

import json
import os
import queue
import signal
import subprocess
import sys
import threading

import testing


class Instance(testing.Instance):
    flags_off = ["extensions", "full", "postgresql", "sshd", "uninstall", "upgrade"]

    install_commit = "HEAD"
    tested_commit = "HEAD"

    def __init__(self, arguments, frontend):
        super(Instance, self).__init__()
        self.arguments = arguments
        self.frontend = frontend
        self.mailbox = None
        self.process = None
        self.hostname = "localhost"
        self.queue = queue.Queue()
        self.registeruser("admin")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self.process:
            self.stop()
        return super().__exit__(*exc_info)

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

    def criticctl(self, argv, *, stdin_data=None):
        if self.arguments.debug:
            argv = ["--verbose", *argv]

        for index, arg in enumerate(argv):
            if arg[0] == "'" == arg[-1]:
                argv[index] = arg[1:-1]

        argv = [self.criticctl_path, *argv]

        testing.logger.debug("Running: %s" % " ".join(argv))

        if stdin_data is None:
            stdin_mode = subprocess.DEVNULL
        else:
            stdin_mode = subprocess.PIPE

        env = os.environ.copy()
        env["CRITIC_HOME"] = self.state_dir

        process = subprocess.Popen(
            argv,
            stdin=stdin_mode,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            env=env,
        )

        stdout, stderr = process.communicate(stdin_data)

        for line in stdout.splitlines():
            testing.logger.log(testing.STDOUT, line)
        for line in stderr.splitlines():
            testing.logger.log(testing.STDERR, line)

        if process.returncode == 0:
            return stdout
        else:
            raise testing.CriticctlError(" ".join(argv), stdout, stderr)

    def has_flag(self, flag):
        return testing.has_flag("HEAD", flag)

    def repository_path(self, repository="critic"):
        return os.path.join(self.state_dir, "git/%s.git" % repository)

    def repository_url(self, name=None, repository="critic"):
        path = self.repository_path(repository)
        if name is None:
            return path
        return testing.repository.RepositoryURL(path, REMOTE_USER=name)

    def readline(self):
        return self.queue.get()

    def install(
        self,
        repository,
        override_arguments={},
        other_cwd=False,
        quick=False,
        interactive=False,
    ):
        argv = [
            sys.executable,
            "-u",
            "quickstart.py",
            "--testing",
            "--state-dir",
            self.state_dir,
        ]

        if self.arguments.debug:
            argv.append("--debug")

        argv.extend(
            [
                "--admin-username",
                "admin",
                "--admin-fullname",
                "Testing Administrator",
                "--admin-email",
                "admin@example.org",
                "--admin-password",
                "testing",
                "--system-recipient",
                "system@example.org",
                "--enable-maildelivery",
                "--http-port",
                str(self.arguments.http_port),
                "--http-lb-backends=1",
                "--smtp-port",
                str(self.mailbox.port),
                "--smtp-username",
                self.mailbox.credentials["username"],
                "--smtp-password",
                self.mailbox.credentials["password"],
            ]
        )

        testing.logger.debug("Running: %s" % " ".join(argv))

        self.process = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
        )

        def consume(stream, loglevel):
            try:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line.startswith("<<<") and line.endswith(">>>"):
                        self.queue.put(line[3:-3])
                    else:
                        testing.logger.log(loglevel, line)
            except IOError:
                pass
            self.queue.put(None)

        stdout_thread = threading.Thread(
            target=consume, args=(self.process.stdout, testing.STDOUT)
        )
        stdout_thread.daemon = True
        stdout_thread.start()

        stderr_thread = threading.Thread(
            target=consume, args=(self.process.stderr, testing.STDERR)
        )
        stderr_thread.daemon = True
        stderr_thread.start()

        def read_output(expected_key):
            line = self.readline()
            if line is None:
                raise testing.InstanceError("Quickstart process died!")
            key, _, value = line.partition("=")
            if key != expected_key:
                raise testing.InstanceError("Unexpected output: %r" % line)
            return value

        testing.logger.debug("State directory: %s" % self.state_dir)

        self.criticctl_path = read_output("CRITICCTL")

        listening_address = read_output("HTTP")
        hostname, _, port = listening_address.partition(":")

        self.frontend.hostname = hostname
        self.frontend.http_port = int(port)

        testing.logger.debug("HTTP address: %s:%s" % (hostname, port))

        read_output("STARTED")

        # Add some regular users.
        for name in sorted(self.users_to_add):
            self.adduser(name)

        try:
            self.frontend.run_basic_tests()
            self.mailbox.check_empty()
        except testing.TestFailure as error:
            if error.args:
                testing.logger.error("Basic test: %s" % error)

            # If basic tests fail, there's no reason to further test this
            # instance; it seems to be properly broken.
            raise testing.InstanceError

        testing.logger.info(
            "Quick-started Critic in %s (%d)"
            % (self.state_dir, self.frontend.http_port)
        )

    def check_upgrade(self):
        raise testing.NotSupported("quick-started instance can't be upgraded")

    def upgrade(
        self, override_arguments={}, other_cwd=False, quick=False, interactive=False
    ):
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
        argv = [
            os.path.join(self.state_dir, "bin", "python"),
            "-u",
            "-m",
            "critic.base.run_unittest",
        ] + args
        return self.executeProcess(argv, log_stderr=False)

    def gc(self, repository):
        self.executeProcess(
            ["git", "gc", "--prune=now"],
            cwd=os.path.join(self.state_dir, "git", repository),
        )

    def filter_service_logs(self, level, service_names):
        helper = "testing/input/service_log_filter.py"
        logfile_paths = {
            os.path.join(
                self.state_dir, "log/main", service_name + ".log"
            ): service_name
            for service_name in service_names
        }
        data = json.loads(
            self.executeProcess(
                ["python", helper, level] + list(logfile_paths.keys()), log_stdout=False
            )
        )
        return {
            logfile_paths[logfile_path]: entries
            for logfile_path, entries in sorted(data.items())
        }

    def restart(self):
        self.process.send_signal(signal.SIGUSR1)

        line = self.readline()

        if line != "RESTARTED":
            raise testing.InstanceError("Unexpected output: %r" % line)

    def customization(self, action, name):
        argv = [os.path.join(self.state_dir, "bin", "pip"), action]
        module_name = f"critic-{name}-customization"

        if action == "install":
            argv.append(os.path.join(os.path.dirname(__file__), "input", module_name))
        else:
            argv.extend(["--yes", module_name])

        testing.logger.debug("Running: %s", " ".join(argv))

        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        stdout, stderr = process.communicate()

        for line in stdout.splitlines():
            testing.logger.log(testing.STDOUT, line)
        for line in stderr.splitlines():
            testing.logger.log(testing.STDERR, line)

        if process.returncode != 0:
            raise testing.TestFailure(" ".join(argv), stdout, stderr)


def setup(subparsers):
    parser = subparsers.add_parser(
        "quickstart",
        description="Test against a quickstarted Critic instance.",
        help=(
            "Start Critic using the `quickstart.py` script, and run tests "
            "against it. This flavor of testing supports almost all tests, "
            "and can be performed as a regular user with very limited "
            "preparations."
        ),
    )
    parser.add_argument(
        "--http-port", type=int, default=0, help="HTTP port [default=random]"
    )
    parser.set_defaults(flavor="quickstart")
