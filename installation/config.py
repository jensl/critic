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

import installation
import os
import os.path
import json

auth_mode = "host"

def prepare(arguments):
    global auth_mode

    if installation.prereqs.bcrypt_available:

        def check(value):
            if value.strip() not in ("host", "critic"):
                return "must be one of 'host' and 'critic'"

        if arguments.auth_mode:
            error = check(arguments.auth_mode)
            if error:
                print "Invalid --auth-mode argument: %s." % arguments.auth_mode
                return False
            auth_mode = arguments.auth_mode
        else:
            print """
Critic Installation: Authentication
===================================

Critic needs to identify (via HTTP authentication) users who access
the Web front-end.  This can be handled in two different ways:

  host    The Web server (Apache) handles authentication and Critic
          only makes use of the user name that it reports via the
          WSGI API.

  critic  Critic implements HTTP authentication itself using passwords
          stored (encrypted) in its database.
"""

            auth_mode = installation.input.string("Which authentication mode should be used?",
                                                  default="critic", check=check)

    return True

created_file = []
created_dir = []

def execute():
    source_dir = os.path.join("installation", "templates", "configuration")
    target_dir = os.path.join(installation.paths.etc_dir, "main", "configuration")

    os.mkdir(target_dir, 0750)
    created_dir.append(target_dir)

    os.chown(target_dir, installation.system.uid, installation.system.gid)

    with open(".install.data") as install_data:
        data = json.load(install_data)

    for entry in os.listdir(source_dir):
        source_path = os.path.join(source_dir, entry)
        target_path = os.path.join(target_dir, entry)

        with open(target_path, "w") as target:
            created_file.append(target_path)

            if entry in ("database.py", "smtp.py"):
                # May contain secrets (passwords.)
                mode = 0600
            else:
                # Won't contain secrets.
                mode = 0640

            os.chmod(target_path, mode)
            os.chown(target_path, installation.system.uid, installation.system.gid)

            with open(source_path, "r") as source:
                target.write((source.read().decode("utf-8") % data).encode("utf-8"))

    return True

def undo():
    map(os.unlink, created_file)
    map(os.rmdir, created_dir)
