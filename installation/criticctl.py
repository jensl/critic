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

def prepare(arguments):
    return True

created_file = []

def execute():
    source_path = os.path.join("installation", "templates", "criticctl")
    target_path = os.path.join("/usr", "bin", "criticctl")

    with open(".install.data") as install_data:
        data = json.load(install_data)

    with open(target_path, "w") as target:
        created_file.append(target_path)

        os.chmod(target_path, 0755)
        os.chown(target_path, installation.system.uid, installation.system.gid)

        with open(source_path, "r") as source:
            target.write((source.read().decode("utf-8") % data).encode("utf-8"))

    return True

def undo():
    map(os.unlink, created_file)
