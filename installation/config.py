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
import pwd
import grp

auth_mode = "host"
session_type = None
allow_anonymous_user = False

def prepare(mode, arguments, data):
    global auth_mode, session_type, allow_anonymous_user

    header_printed = False

    if mode == "install":
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
                header_printed = True

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
    else:
        import configuration

        auth_mode = configuration.base.AUTHENTICATION_MODE

        try: session_type = configuration.base.SESSION_TYPE
        except AttributeError: pass

    if auth_mode == "critic":
        if session_type is None:
            def check(value):
                if value.strip() not in ("httpauth", "cookie"):
                    return "must be one of 'http' and 'cookie'"

            if mode == "install" and arguments.session_type:
                error = check(arguments.session_type)
                if error:
                    print "Invalid --session_type argument: %s." % arguments.session_type
                    return False
                session_type = arguments.session_type
            else:
                if not header_printed:
                    header_printed = True
                    print """
Critic Installation: Authentication
==================================="""

                print """
Critic can authenticate users either via HTTP authentication or via a
"Sign in" form and session cookies.  The major difference is that HTTP
authentication requires a valid login to access any page whereas the
other type of authentication supports limited anonymous access.

  httpauth  Use HTTP authentication.

  cookie    Use session cookie based authentication.
"""

                session_type = installation.input.string("Which session type should be used?",
                                                         default="cookie", check=check)
    else:
        session_type = "cookie"

    allow_anonymous_user = auth_mode == "critic" and session_type == "cookie"

    data["installation.config.auth_mode"] = auth_mode
    data["installation.config.session_type"] = session_type
    data["installation.config.allow_anonymous_user"] = allow_anonymous_user

    return True

created_file = []
created_dir = []
renamed = []
modified_files = 0

def install(data):
    source_dir = os.path.join(installation.root_dir, "installation", "templates", "configuration")
    target_dir = os.path.join(installation.paths.etc_dir, "main", "configuration")

    os.mkdir(target_dir, 0750)
    created_dir.append(target_dir)

    os.chown(target_dir, installation.system.uid, installation.system.gid)

    for entry in os.listdir(source_dir):
        if entry.endswith(".py"):
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

def upgrade(arguments, data):
    global modified_files

    source_dir = os.path.join("installation", "templates", "configuration")
    target_dir = os.path.join(data["installation.paths.etc_dir"], arguments.identity, "configuration")

    system_uid = pwd.getpwnam(data["installation.system.username"]).pw_uid
    system_gid = grp.getgrnam(data["installation.system.groupname"]).gr_gid

    no_changes = True

    for entry in os.listdir(source_dir):
        source_path = os.path.join(source_dir, entry)
        target_path = os.path.join(target_dir, entry)
        backup_path = os.path.join(target_dir, "_" + entry)

        source = open(source_path, "r").read().decode("utf-8") % data

        if not os.path.isfile(target_path):
            write_target = True
            no_changes = False
        else:
            if open(target_path).read().decode("utf-8") == source: continue

            no_changes = False

            def generateVersion(label, path):
                if label == "updated":
                    with open(path, "w") as target:
                        target.write(source.encode("utf-8"))

            update_query = installation.utils.UpdateModifiedFile(
                message="""\
A configuration file is about to be updated.  Please check that no
local modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if any configuration options were added in the
updated version, the system will most likely break if you do not
either install the updated version or manually transfer the new
configuration options to the existing version.
""",
                versions={ "current": target_path,
                           "updated": target_path + ".new" },
                options=[ ("i", "install the updated version"),
                          ("k", "keep the current version"),
                          ("d", ("current", "updated")) ],
                generateVersion=generateVersion)

            write_target = update_query.prompt() == "i"

        if write_target:
            print "Updated file: %s" % target_path

            if not arguments.dry_run:
                if os.path.isfile(target_path):
                    os.rename(target_path, backup_path)
                    renamed.append((target_path, backup_path))

                with open(target_path, "w") as target:
                    created_file.append(target_path)
                    if entry in ("database.py", "smtp.py"):
                        # May contain secrets (passwords.)
                        mode = 0600
                    else:
                        # Won't contain secrets.
                        mode = 0640
                    os.chmod(target_path, mode)
                    os.chown(target_path, system_uid, system_gid)
                    target.write(source.encode("utf-8"))

            modified_files += 1

    if no_changes:
        print "No changed configuration files."

    return True

def undo():
    map(os.unlink, created_file)
    map(os.rmdir, created_dir)

    for target, backup in renamed: os.rename(backup, target)

def finish():
    for target, backup in renamed: os.unlink(backup)
