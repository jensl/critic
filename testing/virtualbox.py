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

import subprocess
import time
import logging

import testing

logger = logging.getLogger("critic")

class HostCommandError(testing.InstanceError):
    def __init__(self, command, output):
        super(HostCommandError, self).__init__(
            "HostCommandError: %s\nOutput:\n%s" % (command, output))
        self.command = command
        self.output = output

class GuestCommandError(testing.InstanceError):
    def __init__(self, command, output):
        super(GuestCommandError, self).__init__(
            "GuestCommandError: %s\nOutput:\n%s" % (command, output))
        self.command = command
        self.output = output

class Instance(object):
    def __init__(self, vboxhost, identifier, snapshot, hostname, ssh_port,
                 install_commit=None, upgrade_commit=None, frontend=None):
        self.vboxhost = vboxhost
        self.identifier = identifier
        self.snapshot = snapshot
        self.hostname = hostname
        self.ssh_port = ssh_port
        if install_commit:
            self.install_commit, self.install_commit_description = install_commit
        if upgrade_commit:
            self.upgrade_commit, self.upgrade_commit_description = upgrade_commit
        self.frontend = frontend
        self.mailbox = None
        self.__started = False

        # Check that the identified VM actually exists:
        output = subprocess.check_output(
            ["VBoxManage", "list", "vms"],
            stderr=subprocess.STDOUT)
        if not self.__isincluded(output):
            raise testing.Error("Invalid VM identifier: %s" % identifier)

        # Check that the identified snapshot actually exists (and that there
        # aren't multiple snapshots with the same name):
        count = self.count_snapshots(snapshot)
        if count == 0:
            raise testing.Error("Invalid VM snapshot: %s (not found)" % snapshot)
        elif count > 1:
            raise testing.Error("Invalid VM snapshot: %s (matches multiple snapshots)" % snapshot)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.__started:
            self.stop()
        return False

    def __vmcommand(self, command, *arguments):
        argv = ["VBoxManage", command, self.identifier] + list(arguments)
        try:
            logger.debug("Running: " + " ".join(argv))
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

    def start(self):
        logger.debug("Starting VM: %s ..." % self.identifier)

        self.__vmcommand("snapshot", "restore", self.snapshot)
        self.__vmcommand("startvm", "--type", "headless")
        self.__started = True

        logger.debug("Waiting for VM to come online ...")

        while True:
            try:
                self.execute(["true"], timeout=1)
            except GuestCommandError:
                time.sleep(0.5)
            else:
                break

        logger.info("Started VM: %s" % self.identifier)

    def stop(self):
        logger.debug("Stopping VM: %s ..." % self.identifier)

        self.__vmcommand("controlvm", "poweroff")

        while self.state() != "poweroff":
            time.sleep(0.1)

        # It appears the VirtualBox "session" can be locked for a while after
        # the "controlvm poweroff" command, and possibly after the VM state
        # changes to "poweroff", so sleep a little longer to avoid problems.
        time.sleep(0.5)

        logger.info("Stopped VM: %s" % self.identifier)

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

    def execute(self, argv, cwd=None, timeout=None):
        guest_argv = list(argv)
        if cwd is not None:
            guest_argv[:0] = ["cd", cwd, "&&"]
        host_argv = ["ssh", "-n", "-p", str(self.ssh_port)]
        if timeout is not None:
            host_argv.extend(["-o", "ConnectTimeout=%d" % timeout])
        host_argv.append(self.hostname)
        try:
            logger.debug("Running: " + " ".join(host_argv + guest_argv))
            return subprocess.check_output(host_argv + guest_argv,
                                           stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            raise GuestCommandError(" ".join(argv), error.output)

    def adduser(self, name, email=None, fullname=None, password=None):
        if email is None:
            email = "%s@example.org" % name
        if fullname is None:
            fullname = "%s von Testing" % name.capitalize()
        if password is None:
            password = "testing"

        # Running all commands with a single self.execute() call is just an
        # optimization; SSH sessions are fairly expensive to start.
        self.execute([
            "sudo", "criticctl", "adduser", "--name", name, "--email", email,
            "--fullname", "'%s'" % fullname, "--password", password,
            "&&",
            "sudo", "adduser", "--ingroup", "critic", "--disabled-password", name,
            "&&",
            "sudo", "mkdir", "/home/%s/.ssh" % name,
            "&&",
            "sudo", "cp", "$HOME/.ssh/authorized_keys", "/home/%s/.ssh" % name,
            "&&",
            "sudo", "chown", "-R", name, "/home/%s/.ssh" % name])

    def install(self, repository, override_arguments={}):
        logger.debug("Installing Critic ...")

        use_arguments = { "--headless": True,
                          "--auth-mode": "critic",
                          "--session-type": "cookie",
                          "--admin-username": "admin",
                          "--admin-email": "admin@example.org",
                          "--admin-fullname": "'Testing Administrator'",
                          "--admin-password": "testing",
                          "--smtp-host": self.vboxhost,
                          "--smtp-port": str(self.mailbox.port),
                          "--smtp-no-ssl-tls": True,
                          "--skip-testmail-check": True, }

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
            logger.debug("Installing Git ...")

            self.execute(["sudo", "DEBIAN_FRONTEND=noninteractive",
                          "apt-get", "-qq", "update"])

            self.execute(["sudo", "DEBIAN_FRONTEND=noninteractive",
                          "apt-get", "-qq", "-y", "install", "git-core"])

            logger.info("Installed Git: %s" % self.execute(["git", "--version"]).strip())

        self.execute(["git", "clone", repository.url, "critic"])
        self.execute(["git", "fetch", "&&",
                      "git", "checkout", self.install_commit],
                     cwd="critic")

        install_output = self.execute(
            ["sudo", "python", "-u", "install.py"] + arguments, cwd="critic")

        logger.debug("Output from install.py:\n" + install_output)

        # Add "developer" role to get stacktraces in error messages.
        self.execute(["sudo", "criticctl", "addrole",
                      "--name", "admin",
                      "--role", "developer"])

        # Add some regular users.
        for name in ("alice", "bob", "dave", "erin"):
            self.adduser(name)

        try:
            self.frontend.run_basic_tests()

            testmail = self.mailbox.pop(
                testing.mailbox.with_subject("Test email from Critic"),
                timeout=3)

            if not testmail:
                testing.expect.check("<test email>", "<no test email received>")
            else:
                testing.expect.check("admin@example.org",
                                     testmail.header("To"))
                testing.expect.check("This is the configuration test email from Critic.",
                                     "\n".join(testmail.lines))

            othermail = self.mailbox.pop()

            if othermail:
                testing.expect.check("<no other email>",
                                     "<email with subject: %s>" % othermail.header("Subject"))
        except testing.TestFailure as error:
            if error.message:
                logger.error("Basic test: %s" % error.message)

            # If basic tests fail, there's no reason to further test this
            # instance; it seems to be properly broken.
            raise testing.InstanceError

        logger.info("Installed Critic: %s" % self.install_commit_description)

    def upgrade(self, override_arguments={}):
        if self.upgrade_commit:
            logger.debug("Upgrading Critic ...")

            use_arguments = { "--headless": True }

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

            upgrade_output = self.execute(
                ["sudo", "python", "-u", "upgrade.py"] + arguments, cwd="critic")

            logger.debug("Output from upgrade.py:\n" + upgrade_output)

            self.frontend.run_basic_tests()

            logger.info("Upgraded Critic: %s" % self.upgrade_commit_description)

    def restart(self):
        self.execute(["sudo", "service", "apache2", "restart"])
        self.execute(["sudo", "service", "critic-main", "restart"])

        # Need to give the service manager a little bit of time to actually
        # start all the background services.
        time.sleep(1)
