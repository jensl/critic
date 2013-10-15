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
import time
import tempfile
import shutil
import subprocess

import testing

class GitCommandError(testing.TestFailure):
    def __init__(self, command, output):
        super(GitCommandError, self).__init__(
            "GitCommandError: %s\nOutput:\n  %s"
            % (command, "\n  ".join(output.strip().splitlines())))
        self.command = command
        self.output = output

def _git(args, **kwargs):
    argv = ["git"] + args
    testing.logger.debug("Running: %s" % " ".join(argv))
    try:
        return subprocess.check_output(
            argv, stdin=open("/dev/null"), stderr=subprocess.STDOUT, **kwargs)
    except subprocess.CalledProcessError as error:
        raise GitCommandError(" ".join(argv), error.output)

class Repository(object):
    def __init__(self, host, port, tested_commit, vm_hostname):
        self.host = host
        self.port = port
        self.base_path = tempfile.mkdtemp()
        self.path = os.path.join(self.base_path, "critic.git")
        self.work = os.path.join(self.base_path, "work")

        if port:
            self.url = "git://%s:%d/critic.git" % (host, port)
        else:
            self.url = "git://%s/critic.git" % host

        testing.logger.debug("Creating temporary repository: %s" % self.path)

        _git(["clone", "--bare", os.getcwd(), "critic.git"],
             cwd=self.base_path)

        _git(["config", "receive.denyDeletes", "false"],
             cwd=self.path)
        _git(["config", "receive.denyNonFastforwards", "false"],
             cwd=self.path)

        _git(["push", "--quiet", "--force", self.path,
              "%s:refs/heads/master" % tested_commit])

    def export(self):
        argv = ["git", "daemon", "--reuseaddr", "--export-all",
                "--base-path=%s" % self.base_path]
        if self.port:
            argv.append("--port=%d" % self.port)
        argv.append(self.path)

        self.daemon = subprocess.Popen(argv)

        time.sleep(1)

        pid, status = os.waitpid(self.daemon.pid, os.WNOHANG)
        if pid != 0:
            self.daemon = None
            testing.logger.error("Failed to export repository!")
            return False

        testing.logger.info("Exported repository: %s" % self.path)
        return True

    def run(self, args):
        return _git(args, cwd=self.path)

    def workcopy(self, name="critic", empty=False):
        class Workcopy(testing.Context):
            def __init__(self, path, start, finish):
                super(Workcopy, self).__init__(start, finish)
                self.path = path

            def run(self, args, **kwargs):
                env = os.environ.copy()
                for name in kwargs.keys():
                    if name.lower() != name == name.upper():
                        env[name] = kwargs[name]
                        del kwargs[name]
                return _git(args, cwd=self.path, env=env, **kwargs)

        path = os.path.join(self.work, name)

        if os.path.exists(path):
            raise testing.InstanceError(
                "Can't create work copy; path already exists!")

        def start():
            if not os.path.isdir(self.work):
                os.mkdir(self.work)
            if not empty:
                _git(["clone", self.path, name], cwd=self.work)
            else:
                os.mkdir(path)
                _git(["init"], cwd=path)

        def finish():
            shutil.rmtree(path)

        return Workcopy(path, start, finish)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.daemon:
                self.daemon.terminate()
                self.daemon.wait()
        except:
            testing.logger.exception("Repository clean-up failed!")

        try:
            shutil.rmtree(self.base_path)
        except:
            testing.logger.exception("Repository clean-up failed!")

        return False
