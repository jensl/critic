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
import json
import sys

from critic import api
from critic import auth
from critic import base
from critic import background
from critic import dbutils
from critic import gitutils

from .extension import Extension


def get_process_params(settings, flavor):
    executable = settings.extensions.flavors[flavor]["executable"]
    library = os.path.join(
        base.configuration()["paths.home"],
        "library",
        settings.extensions.flavors[flavor]["library"],
    )

    return {"argv": [executable, "critic-launcher.js"], "cwd": library}


class ProcessException(Exception):
    pass


class ProcessError(ProcessException):
    def __init__(self, message):
        super(ProcessError, self).__init__("Failed to execute process: %s" % message)


class ProcessTimeout(ProcessException):
    def __init__(self, timeout):
        super(ProcessTimeout, self).__init__(
            "Process timed out after %d seconds" % timeout
        )


class ProcessFailure(ProcessException):
    def __init__(self, returncode, stderr):
        super(ProcessFailure, self).__init__(
            "Process returned non-zero exit status %d" % returncode
        )
        self.returncode = returncode
        self.stderr = stderr


def executeProcess(
    db,
    manifest,
    role_name,
    script,
    function,
    extension_id,
    user_id,
    argv,
    timeout,
    stdin=None,
    rlimit_rss=256,
):
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
        authentication_labels = auth.Database.get().getAuthenticationLabels(user)
        profiles = [auth.AccessControlProfile.forUser(db, user, authentication_labels)]
    else:
        authentication_labels = db.authentication_labels
        profiles = db.profiles

    extension = Extension.fromId(db, extension_id)
    if not auth.AccessControlProfile.isAllowedExtension(profiles, "execute", extension):
        raise auth.AccessDenied(
            "Access denied to extension: execute %s" % extension.getKey()
        )

    flavors = api.critic.settings().extensions.flavors
    flavor = manifest.flavor

    if manifest.flavor not in flavors:
        flavor = api.critic.settings().extensions.default_flavor

    stdin_data = "%s\n" % json.dumps(
        {
            "library_path": flavors[flavor].get("library"),
            "rlimit": {"rss": rlimit_rss},
            "hostname": api.critic.settings().system.hostname,
            "dbparams": base.configuration()["database.parameters"],
            "git": gitutils.git(),
            "python": api.critic.settings().executables.python or sys.executable,
            "repository_work_copy_path": api.critic.settings().extensions.workcopy_dir,
            "changeset_address": background.utils.service_address("changeset"),
            "branchtracker_pid_path": background.utils.service_pidfile("branchtracker"),
            "maildelivery_pid_path": background.utils.service_pidfile("maildelivery"),
            "is_development": api.critic.settings().system.is_development,
            "extension_path": manifest.path,
            "extension_id": extension_id,
            "user_id": user_id,
            "authentication_labels": list(authentication_labels),
            "role": role_name,
            "script_path": script,
            "fn": function,
            "argv": argv,
        }
    )

    if stdin is not None:
        stdin_data += stdin

    command = {"stdin_data": stdin_data, "flavor": flavor, "timeout": timeout}

    # Double the timeout. Timeouts are primarily handled by the extension runner
    # service, which returns an error response on timeout. This timeout here is
    # thus mostly to catch the extension runner service itself timing out.
    command_timeout = timeout * 2

    try:
        response = db.critic.now(
            background.utils.issue_command("extensionrunner", command, command_timeout)
        )
    except background.utils.TimeoutError:
        raise ProcessTimeout(command_timeout)

    if response["status"] == "timeout":
        raise ProcessTimeout(timeout)

    if response["status"] == "error":
        raise ProcessError(response["error"])

    if response["returncode"] != 0:
        raise ProcessFailure(response["returncode"], response["stderr"])

    return response["stdout"].encode("latin-1")
