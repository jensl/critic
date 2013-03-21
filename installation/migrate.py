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

import os
import sys
import json

import installation

def scripts_to_run(data):
    git = data["installation.prereqs.git"]
    old_sha1 = data["sha1"]
    performed_migrations = data.get("migrations", [])
    scripts = []

    if os.path.exists("installation/migrations"):
        for script in os.listdir("installation/migrations"):
            if not script.endswith(".py"):
                continue
            if script in performed_migrations:
                continue

            script_path = os.path.join("installation/migrations", script)

            if installation.utils.get_file_sha1(git, old_sha1, script_path) is not None:
                # The migration script already existed when Critic was installed
                # and there's thus no point in running it now.
                continue

            scripts.append(script)

    return scripts

def will_modify_dbschema(data):
    for script in scripts_to_run(data):
        if script.startswith("dbschema."):
            return True
    return False

def upgrade(arguments, data):
    if "migrations" not in data:
        data["migrations"] = []

    for script in scripts_to_run(data):
        script_path = os.path.join("installation/migrations", script)

        print
        print "Running %s ..." % script

        if arguments.dry_run:
            continue

        env = os.environ.copy()

        # This is "/etc/critic/main", set by upgrade.py, or something else
        # if the --etc-dir/--identity arguments were used.
        env["PYTHONPATH"] = sys.path[0]

        installation.process.check_input([sys.executable, script_path,
                                          "--uid=%s" % installation.system.uid,
                                          "--gid=%d" % installation.system.gid],
                                         stdin=json.dumps(data), env=env)

        data["migrations"].append(script)

    return True
