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
import logging
import subprocess

import testing

logger = logging.getLogger("critic")

class GitCommandError(testing.TestFailure):
    def __init__(self, command, output):
        super(GitCommandError, self).__init__(
            "GitCommandError: %s\nOutput:\n  %s"
            % (command, "\n  ".join(output.strip().splitlines())))
        self.command = command
        self.output = output

def _git(args, **kwargs):
    argv = ["git"] + args
    try:
        return subprocess.check_output(
            argv, stderr=subprocess.STDOUT, **kwargs)
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

        logger.debug("Creating temporary repository: %s" % self.path)

        _git(["clone", "--bare", os.getcwd(), "critic.git"],
             cwd=self.base_path)

        _git(["push", "--quiet", self.path,
              "%s:refs/heads/tested" % tested_commit])

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
            logger.error("Failed to export repository!")
            return False

        logger.info("Exported repository: %s" % self.path)
        return True

    def run(self, args):
        return _git(args, cwd=self.path)

    def workcopy(self, name="work"):
        class Workcopy(object):
            def __init__(self, path):
                self.path = path
            def __enter__(self):
                return self
            def __exit__(self, *args):
                shutil.rmtree(self.path)
                return False
            def run(self, args):
                return _git(args, cwd=self.path)

        path = os.path.join(self.base_path, name)

        if os.path.exists(path):
            raise testing.InstanceError(
                "Can't create work copy; path already exists!")

        _git(["clone", os.getcwd(), name], cwd=self.base_path)

        return Workcopy(path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if self.daemon:
                self.daemon.terminate()
                self.daemon.wait()
        except:
            logger.exception("Repository clean-up failed!")

        try:
            shutil.rmtree(self.base_path)
        except:
            logger.exception("Repository clean-up failed!")

        return False
