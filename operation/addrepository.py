# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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
import os
import os.path
import signal

import dbutils
import gitutils
import configuration

from operation import Operation, OperationResult, OperationError, OperationFailure, Optional

class AddRepository(Operation):
    def __init__(self):
        Operation.__init__(self, { "name": str,
                                   "path": str,
                                   "remote": Optional({ "url": str,
                                                        "branch": str }) })

    def process(self, db, user, name, path, remote=None):
        if not user.hasRole(db, "repositories"):
            raise OperationFailure(code="notallowed",
                                   title="Not allowed!",
                                   message="Only users with the 'repositories' role can add new repositories.")

        path = path.strip("/").rsplit("/", 1)

        if len(path) == 2: base, name = path
        else: base, name = None, path[0]

        if base:
            main_base_path = os.path.join(configuration.paths.GIT_DIR, base)
            relay_base_path = os.path.join(configuration.paths.DATA_DIR, "relay", base)
        else:
            main_base_path = configuration.paths.GIT_DIR
            relay_base_path = os.path.join(configuration.paths.DATA_DIR, "relay")

        main_path = os.path.join(main_base_path, name + ".git")
        relay_path = os.path.join(relay_base_path, name)

        if not os.path.isdir(main_base_path):
            os.makedirs(main_base_path, mode=0775)
        if not os.path.isdir(relay_base_path):
            os.makedirs(relay_base_path, mode=0775)

        def git(arguments, cwd):
            argv = [configuration.executables.GIT] + arguments
            git = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
            stdout, stderr = git.communicate()
            if git.returncode != 0:
                raise OperationError, "'%s' failed: %s" % (" ".join(argv), stderr)

        git(["init", "--bare", "--shared", name + ".git"], cwd=main_base_path)
        git(["config", "receive.denyNonFastforwards", "false"], cwd=main_path)
        git(["config", "critic.name", name], cwd=main_path)

        os.symlink(os.path.join(configuration.paths.INSTALL_DIR, "hooks", "pre-receive"), os.path.join(main_path, "hooks", "pre-receive"))

        cursor = db.cursor()
        cursor.execute("""INSERT INTO repositories (name, path, relay)
                               VALUES (%s, %s, %s)
                            RETURNING id""",
                       (name, main_path, relay_path))
        repository_id = cursor.fetchone()[0]

        if remote:
            cursor.execute("""INSERT INTO trackedbranches (repository, local_name, remote, remote_name, forced, delay)
                                   VALUES (%s, '*', %s, '*', true, '1 day')""",
                           (repository_id, remote["url"]))
            cursor.execute("""INSERT INTO trackedbranches (repository, local_name, remote, remote_name, forced, delay)
                                   VALUES (%s, %s, %s, %s, true, '1 day')""",
                           (repository_id, remote["branch"], remote["url"], remote["branch"]))

        db.commit()

        if remote:
            pid = int(open(configuration.services.BRANCHTRACKER["pidfile_path"]).read().strip())
            os.kill(pid, signal.SIGHUP)

        return OperationResult()
