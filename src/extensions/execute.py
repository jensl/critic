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
import subprocess

import configuration
import auth
import dbutils

from extensions.extension import Extension
from textutils import json_encode
from communicate import Communicate

def executeProcess(db, manifest, role_name, script, function, extension_id,
                   user_id, argv, timeout, stdin=None, rlimit_rss=256):
    # If |user_id| is not the same as |db.user|, then one user's access of the
    # system is triggering an extension on behalf of another user.  This will
    # for instance happen when one user is adding changes to a review,
    # triggering an extension filter hook set up by another user.
    #
    # In this case, we need to check that the other user can access the
    # extension.
    #
    # If |user_id| is the same as |db.user|, we need to use |db.profiles|, which
    # may contain a profile associated with an access token that was used to
    # authenticate the user.
    if user_id != db.user.id:
        user = dbutils.User.fromId(db, user_id)
        profiles = [auth.AccessControlProfile.forUser(db, user)]
    else:
        profiles = db.profiles

    extension = Extension.fromId(db, extension_id)
    if not auth.AccessControlProfile.isAllowedExtension(
            profiles, "execute", extension):
        raise auth.AccessDenied("Access denied to extension: execute %s"
                                % extension.getKey())

    flavor = manifest.flavor

    if manifest.flavor not in configuration.extensions.FLAVORS:
        flavor = configuration.extensions.DEFAULT_FLAVOR

    executable = configuration.extensions.FLAVORS[flavor]["executable"]
    library = configuration.extensions.FLAVORS[flavor]["library"]

    process_argv = [executable, os.path.join(library, "critic-launcher.js")]

    stdin_data = "%s\n" % json_encode({
            "criticjs_path": os.path.join(library, "critic.js"),
            "rlimit": { "rss": rlimit_rss },
            "hostname": configuration.base.HOSTNAME,
            "dbname": configuration.database.PARAMETERS["database"],
            "dbuser": configuration.database.PARAMETERS["user"],
            "git": configuration.executables.GIT,
            "python": configuration.executables.PYTHON,
            "python_path": "%s:%s" % (configuration.paths.CONFIG_DIR,
                                      configuration.paths.INSTALL_DIR),
            "repository_work_copy_path": configuration.extensions.WORKCOPY_DIR,
            "changeset_address": configuration.services.CHANGESET["address"],
            "branchtracker_pid_path": configuration.services.BRANCHTRACKER["pidfile_path"],
            "maildelivery_pid_path": configuration.services.MAILDELIVERY["pidfile_path"],
            "is_development": configuration.debug.IS_DEVELOPMENT,
            "extension_path": manifest.path,
            "extension_id": extension_id,
            "user_id": user_id,
            "role": role_name,
            "script_path": script,
            "fn": function,
            "argv": argv })

    if stdin is not None:
        stdin_data += stdin

    process = subprocess.Popen(process_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=manifest.path)

    communicate = Communicate(process)
    communicate.setInput(stdin_data)
    communicate.setTimeout(timeout)

    return communicate.run()[0]
