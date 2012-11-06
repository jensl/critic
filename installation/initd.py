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
import os.path
import json

import installation
from installation import process

def prepare(arguments):
    return True

created_file = []
rclinks_added = False
servicemanager_started = False

def execute():
    global servicemanager_started, rclinks_added

    source_path = os.path.join(installation.root_dir, "installation", "templates", "initd")
    target_path = os.path.join("/etc", "init.d", "critic-main")

    with open(os.path.join(installation.root_dir, ".install.data")) as install_data:
        data = json.load(install_data)

    with open(target_path, "w") as target:
        created_file.append(target_path)

        os.chmod(target_path, 0755)
        os.chown(target_path, installation.system.uid, installation.system.gid)

        with open(source_path, "r") as source:
            target.write((source.read().decode("utf-8") % data).encode("utf-8"))

    process.check_call(["update-rc.d", "critic-main", "defaults"])
    rclinks_added = True

    process.check_call([target_path, "start"])
    servicemanager_started = True

    return True

def undo():
    if servicemanager_started:
        process.check_call([os.path.join("/etc", "init.d", "critic-main"), "stop"])

    map(os.unlink, created_file)

    if rclinks_added:
        process.check_call(["update-rc.d", "critic-main", "remove"])
