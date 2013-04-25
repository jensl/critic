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
    if "cwd" in kwargs:
        cwd = " (in %s)" % kwargs["cwd"]
    else:
        cwd = ""
    testing.logger.debug("Running: %s%s" % (" ".join(argv), cwd))
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

        testing.logger.debug("Creating temporary repositories in: %s" % self.base_path)

        _git(["clone", "--bare", os.getcwd(), "critic.git"],
             cwd=self.base_path)

        _git(["config", "receive.denyDeletes", "false"],
             cwd=self.path)
        _git(["config", "receive.denyNonFastforwards", "false"],
             cwd=self.path)

        self.push(tested_commit)

        def submodule_sha1(repository_path, parent_sha1, submodule_path):
            try:
                lstree = _git(["ls-tree", parent_sha1, submodule_path],
                              cwd=repository_path)
            except GitCommandError:
                # Sub-module doesn't exist?  Will probably fail later, but
                # doesn't need to fail here.
                return None
            mode, object_type, sha1, path = lstree.strip().split(None, 3)
            if object_type != "commit":
                # Odd.  The repository doesn't look at all like we expect.
                return None
            return sha1

        if os.path.exists("installation/externals/v8-jsshell/.git"):
            v8_jsshell_path = os.path.join(os.getcwd(), "installation/externals/v8-jsshell")
            _git(["clone", "--bare", v8_jsshell_path, "v8-jsshell.git"],
                 cwd=self.base_path)
            self.v8_jsshell_path = os.path.join(self.base_path, "v8-jsshell.git")
            v8_jsshell_sha1 = submodule_sha1(os.getcwd(), tested_commit,
                                             "installation/externals/v8-jsshell")
            if v8_jsshell_sha1:
                _git(["push", "--quiet", "--force", self.v8_jsshell_path,
                      v8_jsshell_sha1 + ":refs/heads/master"],
                     cwd=v8_jsshell_path)
        else:
            self.v8_jsshell_path = None
            v8_jsshell_sha1 = None

        if os.path.exists("installation/externals/v8-jsshell/v8/.git"):
            v8_path = os.path.join(os.getcwd(), "installation/externals/v8-jsshell/v8")
            _git(["clone", "--bare", v8_path, "v8/v8.git"],
                 cwd=self.base_path)
            self.v8_path = os.path.join(self.base_path, "v8/v8.git")
            if port:
                self.v8_url = "git://%s:%d/v8/v8.git" % (host, port)
            else:
                self.v8_url = "git://%s/v8/v8.git" % host
            if v8_jsshell_sha1:
                v8_sha1 = submodule_sha1("installation/externals/v8-jsshell",
                                         v8_jsshell_sha1, "v8")
                if v8_sha1:
                    _git(["push", "--quiet", "--force", self.v8_path,
                          v8_sha1 + ":refs/heads/master"],
                         cwd=v8_path)
        else:
            self.v8_path = None
            self.v8_url = None

    def push(self, commit):
        _git(["push", "--quiet", "--force", self.path,
              "%s:refs/heads/master" % commit])

    def export(self):
        argv = ["git", "daemon", "--reuseaddr", "--export-all",
                "--base-path=%s" % self.base_path]
        if self.port:
            argv.append("--port=%d" % self.port)
        argv.append(self.path)
        if self.v8_jsshell_path:
            argv.append(self.v8_jsshell_path)
        if self.v8_path:
            argv.append(self.v8_path)

        self.daemon = subprocess.Popen(argv)

        time.sleep(1)

        pid, status = os.waitpid(self.daemon.pid, os.WNOHANG)
        if pid != 0:
            self.daemon = None
            testing.logger.error("Failed to export repository!")
            return False

        testing.logger.debug("Exported repository: %s" % self.path)
        if self.v8_jsshell_path:
            testing.logger.debug("Exported repository: %s" % self.v8_jsshell_path)
        if self.v8_path:
            testing.logger.debug("Exported repository: %s" % self.v8_path)
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
