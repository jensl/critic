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
from textutils import json_encode
from communicate import Communicate

def executeProcess(manifest, role, extension_id, user_id, argv, timeout, stdin=None, rlimit_cpu=5, rlimit_rss=256):
    flavor = manifest.flavor

    if manifest.flavor not in configuration.extensions.FLAVORS:
        flavor = configuration.extensions.DEFAULT_FLAVOR

    executable = configuration.extensions.FLAVORS[flavor]["executable"]
    library = configuration.extensions.FLAVORS[flavor]["library"]

    process_argv = [executable,
                    "--rlimit-cpu=%ds" % rlimit_cpu,
                    "--rlimit-rss=%dm" % rlimit_rss,
                    os.path.join(library, "critic-launcher.js")]

    stdin_data = "%s\n" % json_encode({ "criticjs_path": os.path.join(library, "critic2.js"),
                                        "rlimit": { "cpu": rlimit_cpu,
                                                    "rss": rlimit_rss },
                                        "hostname": configuration.base.HOSTNAME,
                                        "dbname": configuration.database.PARAMETERS["database"],
                                        "dbuser": configuration.database.PARAMETERS["user"],
                                        "git": configuration.executables.GIT,
                                        "python": configuration.executables.PYTHON,
                                        "python_path": "%s:%s" % (configuration.paths.CONFIG_DIR,
                                                                  configuration.paths.INSTALL_DIR),
                                        "repository_work_copy_path": os.path.join(configuration.paths.DATA_DIR, "temporary", "EXTENSIONS"),
                                        "changeset_address": configuration.services.CHANGESET["address"],
                                        "maildelivery_pid_path": configuration.services.MAILDELIVERY["pidfile_path"],
                                        "is_development": configuration.debug.IS_DEVELOPMENT,
                                        "extension_path": manifest.path,
                                        "extension_id": extension_id,
                                        "user_id": user_id,
                                        "role": role.name(),
                                        "script_path": role.script,
                                        "fn": role.function,
                                        "argv": argv })

    if stdin is not None:
        stdin_data += stdin

    process = subprocess.Popen(process_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=manifest.path)

    communicate = Communicate(process)
    communicate.setInput(stdin_data)
    communicate.setTimout(timeout)

    return communicate.run()[0]
