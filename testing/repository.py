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


class RepositoryURL(object):
    def __init__(self, value, **kwargs):
        self.value = value
        self.environ = kwargs

    def __str__(self):
        return self.value


class GitCommandError(testing.TestFailure):
    def __init__(self, command, output):
        super(GitCommandError, self).__init__(
            "GitCommandError: %s\nOutput:\n  %s"
            % (command, "\n  ".join(output.strip().splitlines()))
        )
        self.command = command
        self.output = output


def _git(args, **kwargs):
    if "cwd" in kwargs:
        cwd = " (in %s)" % kwargs["cwd"]
    else:
        cwd = ""
    env = os.environ.copy()
    for name, value in kwargs.get("env", {}).items():
        if value is None:
            if name in env:
                del env[name]
        else:
            env[name] = value
    env.setdefault("GIT_AUTHOR_NAME", "Critic Tester")
    env.setdefault("GIT_COMMITTER_NAME", "Critic Tester")
    env.setdefault("GIT_AUTHOR_EMAIL", "tester@example.org")
    env.setdefault("GIT_COMMITTER_EMAIL", "tester@example.org")

    def process(arg):
        if isinstance(arg, RepositoryURL):
            for key, value in arg.environ.items():
                testing.logger.debug("Overriding environment: %s=%r", key, value)
            env.update(arg.environ)
        return str(arg)

    argv = ["git"]
    argv.extend(process(arg) for arg in args)
    kwargs["env"] = env
    testing.logger.debug("Running: %s%s" % (" ".join(argv), cwd))
    try:
        return testing.execute.execute(argv, mix_stdout_and_stderr=True, **kwargs)
    except testing.CommandError as error:
        raise GitCommandError(" ".join(argv), error.stdout)


def submodule_sha1(repository_path, parent_sha1, submodule_path):
    try:
        lstree = _git(["ls-tree", parent_sha1, submodule_path], cwd=repository_path)
    except GitCommandError:
        # Sub-module doesn't exist?  Will probably fail later, but doesn't need
        # to fail here.
        return None
    mode, object_type, sha1, path = lstree.strip().split(None, 3)
    if object_type != "commit":
        # Odd.  The repository doesn't look at all like we expect.
        return None
    return sha1


class Repository(object):
    instance = None

    def __init__(self, host, port, tested_commit, instance):
        Repository.instance = self

        self.port = port
        self.instance = instance
        self.base_path = tempfile.mkdtemp()
        self.path = os.path.join(self.base_path, "critic.git")
        self.work = os.path.join(self.base_path, "work")

        self.set_host(host)

        testing.logger.debug("Creating temporary repositories in: %s" % self.base_path)

        _git(["clone", "--bare", os.getcwd(), "critic.git"], cwd=self.base_path)
        _git(
            ["init", "--bare", "email-notifications.git"], cwd=self.base_path,
        )
        sha1 = _git(
            ["subtree", "split", "-q", "-P", "extensions/email-notifications"]
        ).strip()
        _git(
            [
                "push",
                os.path.join(self.base_path, "email-notifications.git"),
                f"{sha1}:refs/heads/master",
            ]
        )

        _git(["config", "receive.denyDeletes", "false"], cwd=self.path)
        _git(["config", "receive.denyNonFastforwards", "false"], cwd=self.path)

        self.push(tested_commit)

    def set_host(self, host):
        self.host = host

    def url(self, name="critic"):
        base = f"git://{self.host}"
        if self.port:
            base += f":{self.port}"
        return f"{base}/{name}.git"

    def push(self, commit):
        _git(["push", "--quiet", "--force", self.path, "%s:refs/heads/master" % commit])

    def export(self):
        argv = [
            "git",
            "daemon",
            "--reuseaddr",
            "--export-all",
            "--base-path=%s" % self.base_path,
            self.base_path,
        ]
        if self.port:
            argv.append("--port=%d" % self.port)

        self.daemon = subprocess.Popen(argv)

        time.sleep(1)

        pid, status = os.waitpid(self.daemon.pid, os.WNOHANG)
        if pid != 0:
            self.daemon = None
            testing.logger.error("Failed to export repository!")
            return False

        testing.logger.debug("Exported repository: %s" % self.path)
        return True

    def run(self, args, *, cwd=None, env=None):
        if cwd is None:
            cwd = self.path
        if env is None:
            env = {}
        return _git(args, cwd=cwd, env=env)

    def workcopy(self, *, name="work", clone=None, empty=False):
        master = self

        class Workcopy(testing.Context):
            def __init__(self, path, clone, start, finish):
                super(Workcopy, self).__init__(start, finish)
                self.path = path
                self.clone_of = clone or "critic"
                self.files = {}

            def run(self, *args, **kwargs):
                if len(args) == 1 and isinstance(args[0], list):
                    args = args[0]
                if kwargs:
                    env = {
                        name: value
                        for name, value in kwargs.items()
                        if name.lower() != name == name.upper()
                    }
                    for name in env.keys():
                        del kwargs[name]
                else:
                    env = None
                return master.run(args, cwd=self.path, env=env, **kwargs)

            def revparse(self, ref="HEAD"):
                return self.run(["rev-parse", ref + "^{commit}"]).strip()

            def add(self, **files):
                self.files.update(files)

            def commit(self, message, **files):
                for filename, content in files.items():
                    filename = self.files.get(filename, filename)
                    fullpath = os.path.join(self.path, filename)
                    directory = os.path.dirname(fullpath)

                    if not os.path.isdir(directory):
                        os.makedirs(directory)

                    with open(fullpath, "w") as fileobj:
                        fileobj.write(content)

                    self.run(["add", filename])

                self.run(["commit", "-m" + message, "--allow-empty"])
                return self.revparse()

        path = os.path.join(self.work, name)

        if os.path.exists(path):
            raise testing.InstanceError("Can't create work copy; path already exists!")

        def start():
            if not os.path.isdir(self.work):
                os.mkdir(self.work)
            if not empty:
                if clone is None:
                    url = self.path
                else:
                    url = self.instance.repository_url(repository=clone)
                _git(["clone", url, name], cwd=self.work)
            else:
                os.mkdir(path)
                _git(["init"], cwd=path)

        def finish():
            shutil.rmtree(path)

        return Workcopy(path, clone, start, finish)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
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
