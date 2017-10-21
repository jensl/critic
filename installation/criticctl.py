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

criticctl_path = None
created_file = []
renamed = []

def install(data):
    global criticctl_path

    source_path = os.path.join(installation.root_dir, "installation", "templates", "criticctl")
    target_path = criticctl_path = os.path.join(installation.paths.bin_dir, "criticctl")

    with open(target_path, "w") as target:
        created_file.append(target_path)

        os.chmod(target_path, 0o755)

        with open(source_path, "r") as source:
            target.write((source.read().decode("utf-8") % data).encode("utf-8"))

    return True

def upgrade(arguments, data):
    target_path = os.path.join(installation.paths.bin_dir, "criticctl")
    backup_path = installation.utils.update_from_template(
        arguments, data,
        template_path="installation/templates/criticctl",
        target_path=target_path,
        message="""\
The criticctl utility is about to be updated.  Please check that no local
modifications are being overwritten.

%(versions)s

Please note that if the modifications are not installed, the criticctl utility
is likely to stop working.
""")

    if backup_path:
        created_file.append(target_path)
        renamed.append((target_path, backup_path))

    return True

def undo():
    map(os.unlink, created_file)

    for target, backup in renamed:
        os.rename(backup, target)

def finish(mode, arguments, data):
    for target, backup in renamed:
        os.unlink(backup)
