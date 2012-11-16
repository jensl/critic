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

def will_modify_dbschema(data):
    performed_migrations = data.get("migrations", [])

    if os.path.exists("installation/migrations"):
        for script in os.listdir("installation/migrations"):
            if script.startswith("dbschema.") \
                    and script.endswith(".py") \
                    and script not in performed_migrations:
                return True

    return False

def upgrade(arguments, data):
    if "migrations" not in data:
        data["migrations"] = []

    if os.path.exists("installation/migrations"):
        for script in os.listdir("installation/migrations"):
            if not script.endswith(".py"): continue
            if script in data["migrations"]: continue

            print
            print "Running %s ..." % script

            if arguments.dry_run: continue

            installation.process.check_input([sys.executable, os.path.join("installation/migrations", script),
                                              "--uid=%s" % installation.system.uid,
                                              "--gid=%d" % installation.system.gid],
                                             stdin=json.dumps(data))

            data["migrations"].append(script)

    return True
