# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2018 the Critic contributors, Opera Software ASA
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

import distutils.spawn
import errno
import glob
import grp
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time

import testing


class Instance(testing.Instance):
    def __init__(self, arguments, *, frontend=None):
        super().__init__()
        self.arguments = arguments
        self.frontend = frontend
        self.workdir = None
        self.up = False

        self.__docker_path = distutils.spawn.find_executable("docker")
        if not self.__docker_path:
            raise testing.InstanceError("no 'docker' executable found")

        self.__compose_path = os.path.join(sys.prefix, "bin", "docker-compose")
        if not os.access(self.__compose_path, os.X_OK):
            self.__compose_path = distutils.spawn.find_executable("docker-compose")
            if not self.__compose_path:
                raise testing.InstanceError("no 'docker-compose' executable found")

        if os.getuid() == 0:
            self.__use_sudo = False
        else:
            try:
                docker_gid = grp.getgrnam("docker").gr_gid
            except KeyError:
                self.__use_sudo = True
            else:
                self.__use_sudo = docker_gid not in os.getgroups()

        if self.__use_sudo:
            testing.logger.info("Current user not member of 'docker' group.")
            testing.logger.info("Will use 'sudo' to run 'docker'/'docker-compose'.")

        self.__follow_logs_pid = {}

        self.__condition = threading.Condition()
        self.__is_restarting = False
        self.__is_stopping = False

    def __docker(self, *arguments, **kwargs):
        argv = [self.__docker_path] + list(arguments)
        if self.__use_sudo:
            argv.insert(0, "sudo")
        kwargs.setdefault("cwd", self.workdir)
        kwargs.setdefault("log_stdout", False)
        testing.logger.debug("Running: %s", " ".join(argv))
        return testing.execute.execute(argv, **kwargs)

    def __compose(self, *arguments, **kwargs):
        argv = [self.__compose_path, "--no-ansi"] + list(arguments)
        if self.__use_sudo:
            argv.insert(0, "sudo")
        kwargs.setdefault("cwd", self.workdir)
        kwargs.setdefault("log_stdout", False)
        testing.logger.debug("Running: %s", " ".join(argv))
        return testing.execute.execute(argv, **kwargs)

    def __execute(self, *arguments, stdin_data=None):
        return self.__compose(
            "exec", "-T", "services", *arguments, stdin_data=stdin_data
        )

    def __dockerfile(self, flavor):
        return f"docker/dockerfiles/Dockerfile.{flavor}"

    def __wait(self, host, port, timeout=30):
        deadline = time.time() + timeout
        first_timeout = True
        first_refused = True
        while True:
            try:
                connection = socket.create_connection((host, port), timeout=1)
            except socket.timeout:
                if first_timeout:
                    testing.logger.debug(
                        "Connection attempt [%s:%d]: timeout", host, port
                    )
                    first_timeout = False
            except OSError as error:
                if error.errno != errno.ECONNREFUSED:
                    raise
                if first_refused:
                    testing.logger.debug(
                        "Connection attempt [%s:%d]: ECONNREFUSED", host, port
                    )
                    first_refused = False
            else:
                connection.close()
                testing.logger.debug("Connection attempt [%s:%d]: OK", host, port)
                return True
            remaining = deadline - time.time()
            if remaining >= 1:
                time.sleep(1)
            else:
                return False

    def __wait_all(self, timeout=30):
        network = json.loads(
            self.__docker("network", "inspect", f"{self.project}_default")
        )

        self.host_ip = network[0]["IPAM"]["Config"][0]["Gateway"]

        for container in network[0]["Containers"].values():
            ip, _, _ = container["IPv4Address"].partition("/")
            if container["Name"] == f"{self.project}_services_1":
                self.services_ip = ip
            elif container["Name"] == f"{self.project}_sshd_1":
                self.sshd_ip = ip
            elif container["Name"] == f"{self.project}_api_1":
                self.api_ip = ip
                self.frontend.hostname = ip
                self.frontend.http_port = 80

        testing.logger.debug("Host IP: %s", self.host_ip)
        testing.logger.debug("Services IP: %s", self.services_ip)
        testing.logger.debug("SSH access IP: %s", self.sshd_ip)
        testing.logger.debug("API IP: %s", self.api_ip)

        testing.repository.Repository.instance.set_host(self.host_ip)

        if not self.__wait(self.services_ip, 9987, timeout=timeout):
            raise testing.InstanceError("Starting Services timed out!")
        if not self.__wait(self.sshd_ip, 22, timeout=timeout):
            raise testing.InstanceError("Starting SSH access timed out!")
        if not self.__wait(self.api_ip, 80, timeout=timeout):
            raise testing.InstanceError("Starting API timed out!")

    def __follow_logs(self):
        if not self.arguments.follow_logs:
            return

        def follow_logs(service):
            lines_seen = 0
            skip_lines = 0

            def one_line(line):
                nonlocal lines_seen, skip_lines
                if skip_lines:
                    skip_lines -= 1
                    return
                lines_seen += 1
                testing.logger.log(testing.STDOUT, line)

            def collect_pid(pid):
                with self.__condition:
                    self.__follow_logs_pid[service] = pid

            while True:
                skip_lines = lines_seen
                try:
                    self.__compose(
                        "logs",
                        "--follow",
                        service,
                        log_stdout=one_line,
                        pid_callback=collect_pid,
                    )
                except testing.CommandError as error:
                    if error.returncode is not None:
                        if error.returncode > 0:
                            testing.logger.debug(
                                "`docker-compose logs` failed: returncode=%r",
                                error.returncode,
                            )
                        else:
                            testing.logger.debug(
                                "`docker-compose logs` crashed: signal=%r",
                                -error.returncode,
                            )
                else:
                    testing.logger.debug("`docker-compose logs` exited")
                with self.__condition:
                    if self.__is_stopping:
                        return
                    while self.__is_restarting:
                        self.__condition.wait()

        for service in self.arguments.follow_logs:
            threading.Thread(target=follow_logs, args=(service,), daemon=True).start()

    def __restart_follow_logs(self):
        with self.__condition:
            for service, pid in self.__follow_logs_pid.items():
                testing.logger.debug("killing PID=%d", pid)
                os.kill(signal.SIGTERM, pid)

    def start(self):
        self.workdir = tempfile.mkdtemp()
        self.project = os.path.basename(self.workdir)

        testing.execute.execute(["git", "worktree", "add", self.workdir])

        # Create this directory, so that the SSH access service doesn't need to,
        # but mostly so that it isn't created with unhelpful ownership.
        self.__host_keys_dir = os.path.join(self.workdir, "hostkeys")
        os.mkdir(self.__host_keys_dir)

        # Create a minimal dummy "UI build". Tests won't depend on it, but
        # building the Docker images requires that these files/directories
        # exist.
        build_dir = os.path.join(self.workdir, "ui/build")
        os.makedirs(os.path.join(build_dir, "static"))

        def touch(filename):
            open(os.path.join(build_dir, filename), "w").close()

        touch("index.html")
        touch("manifest.json")
        touch("favicon.png")

    def install(self, repository):
        tag = testing.execute.execute(["git", "rev-parse", "--short=8", "HEAD"]).strip()

        build_images = []
        for image in ["postgresql", "services", "sshd", "aiohttp"]:
            image_id = self.__docker("images", "-q", f"critic/{image}:{tag}")
            if not image_id.strip():
                build_images.append(image)

        if build_images:
            make_argv = ["make", "-C", os.path.join(self.workdir, "docker")]
            if self.__use_sudo:
                make_argv.append("docker=sudo docker")
            make_argv.extend(
                [
                    f"tag={tag}",
                    f"flavor={self.arguments.docker_flavor}",
                    "for_testing=yes",
                    "services",
                    "aiohttp",
                    "sshd",
                    "postgresql",
                    "extensionhost",
                ]
            )
            make_argv.extend(build_images)
            testing.execute.execute(make_argv)

        loquacity = []
        if self.arguments.debug:
            loquacity.append("VERBOSE=1")
        elif self.arguments.quiet:
            loquacity.append("QUIET=1")

        services = {
            "database": {
                "image": f"critic/postgresql:{tag}",
                "environment": ["PGDATA=/var/lib/postgresql/data/pgdata"],
                "volumes": ["dbdata:/var/lib/postgresql/data"],
            },
            "services": {
                "image": f"critic/services:{tag}",
                "depends_on": ["database"],
                "environment": [
                    "SYSTEM_HOSTNAME=critic",
                    "DATABASE_HOST=database",
                    "IS_TESTING=1",
                ]
                + loquacity,
                "volumes": ["repositories:/var/git", f"{self.workdir}:/workdir"],
            },
            "sshd": {
                "image": f"critic/sshd:{tag}",
                "depends_on": ["database", "services"],
                "environment": [
                    "DATABASE_HOST=database",
                    "HOST_KEY_ARGS=--host-key-dir=/workdir/hostkeys",
                    "IS_TESTING=1",
                ]
                + loquacity,
                "volumes": ["repositories:/var/git", f"{self.workdir}:/workdir"],
            },
            "api": {
                "image": f"critic/aiohttp:{tag}",
                "depends_on": ["database", "services"],
                "environment": [
                    "SERVICES_HOST=services",
                    "DATABASE_HOST=database",
                    "IS_TESTING=1",
                ]
                + loquacity,
            },
            "extensionhost": {
                "image": f"critic/extensionhost:{tag}",
                "depends_on": ["database", "services"],
                "environment": [
                    "SERVICES_HOST=services",
                    "DATABASE_HOST=database",
                    "IS_TESTING=1",
                ]
                + loquacity,
            }
        }

        if self.arguments.http_port:
            services["api"]["ports"] = [f"127.0.0.1:{self.arguments.http_port}:80"]

        volumes = {"dbdata": {}, "repositories": {}}

        configuration = {"version": "3", "services": services, "volumes": volumes}

        path = os.path.join(self.workdir, "docker-compose.yaml")
        with open(path, "w") as file:
            json.dump(configuration, file)

        self.project = os.path.basename(self.workdir)

        self.__compose("up", "--detach")
        self.__follow_logs()
        self.up = True

        self.__wait_all()

        setting_names = []
        setting_values = ""

        def set_setting(name, value):
            nonlocal setting_names, setting_values
            setting_names.append(name)
            setting_values += json.dumps(value) + "\n"

        set_setting("system.recipients", ["system@example.org"]),
        set_setting("smtp.configured", True),
        set_setting("smtp.address.host", self.host_ip),
        set_setting("smtp.address.port", self.mailbox.port),
        if self.mailbox.credentials:
            set_setting(
                "smtp.credentials.username", self.mailbox.credentials["username"]
            )
            set_setting(
                "smtp.credentials.password", self.mailbox.credentials["password"]
            )

        self.criticctl(["settings", "set"] + setting_names, stdin_data=setting_values)
        self.criticctl(["run-task", "calibrate-pwhash", "--hash-time=0.01"])

        self.__compose("restart", "api", "services")
        self.__wait_all()

        self.adduser("admin")

        with self.frontend.signin():
            for name in sorted(self.users_to_add):
                self.adduser(name, use_http=True)

        self.__execute("/bin/bash", "-c", f"echo '{self.host_ip}\thost' >> /etc/hosts")

        self.__write_known_hosts()

    def __write_known_hosts(self):
        host_keys = glob.glob(os.path.join(self.__host_keys_dir, "*.pub"))
        with open(self.ssh_known_hosts(), "w") as file:
            for filename in host_keys:
                with open(filename) as host_key:
                    file.write(f"{self.sshd_ip} {host_key.read().strip()}\n")

    def upgrade(self):
        pass

    def execute(self, arguments):
        raise testing.NotSupported

    def restart(self):
        with self.__condition:
            self.__is_restarting = True
        self.__compose("restart", "services", "sshd", "api")
        self.__wait_all()
        self.__write_known_hosts()  # The `sshd` container may have a new IP.
        self.__restart_follow_logs()
        with self.__condition:
            self.__is_restarting = False
            self.__condition.notify_all()

    def criticctl(self, arguments, *, stdin_data=None):
        try:
            return self.__execute(
                "/var/lib/critic/bin/criticctl", *arguments, stdin_data=stdin_data
            )
        except testing.CommandError as error:
            raise testing.CriticctlError(
                error.command, error.stdout, error.stderr
            ) from None

    def filter_service_logs(self, level, service_names):
        helper = "testing/input/service_log_filter.py"
        prefix = "/var/log/critic/main"
        logfile_paths = {
            os.path.join(prefix, f"{service_name}.log"): service_name
            for service_name in service_names
        }
        data = json.loads(
            self.__execute("python3", "workdir/" + helper, level, *logfile_paths.keys())
        )
        return {
            logfile_paths[logfile_path]: entries
            for logfile_path, entries in data.items()
        }

    def finish(self):
        pass

    def repository_url(self, name=None, repository="critic", *, via_ssh=False):
        if via_ssh:
            assert name is not None
            return testing.repository.RepositoryURL(
                f"git@critic:{repository}.git",
                GIT_SSH_COMMAND=f"ssh -F {self.ssh_config(for_user=name)}",
            )
        return testing.repository.RepositoryURL(
            f"{self.frontend.prefix(name)}/{repository}.git",
            GIT_ASKPASS=os.path.abspath("testing/password-testing"),
        )

    def sshd_address(self):
        return (self.sshd_ip, 22)

    def __exit__(self, *exc_info):
        with self.__condition:
            self.__is_stopping = True
        if self.up:
            self.__compose("down", "--volumes")
        if self.workdir:
            shutil.rmtree(self.workdir)
        return super().__exit__(*exc_info)


def setup(subparsers):
    parser = subparsers.add_parser(
        "docker",
        description="Test against Critic running containerized using Docker.",
        help=(
            "This flavor of testing can run all tests, with very limited "
            "preparations. Docker must be installed, though, and access to "
            "the Docker daemon must be gained, either using `sudo` or "
            "by running as a user that is a member of the `docker` group."
        ),
    )
    parser.add_argument(
        "--flavor",
        choices=("latest", "alpine"),
        default="latest",
        dest="docker_flavor",
        help="Flavor of Docker images to build and run.",
    )
    parser.add_argument(
        "--follow-log",
        choices=("database", "services", "api", "sshd"),
        action="append",
        dest="follow_logs",
        help="Follow and output logs from selected containers.",
    )
    parser.add_argument(
        "--http-port", type=int, help="Expose the API service's HTTP port on localhost"
    )
    parser.set_defaults(flavor="docker")
