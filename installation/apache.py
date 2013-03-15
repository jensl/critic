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

import installation
from installation import process

pass_auth = "Off"

def prepare(mode, arguments, data):
    global pass_auth

    if installation.config.auth_mode == "critic":
        pass_auth = "On"

    data["installation.apache.pass_auth"] = pass_auth

    return True

created_file = []
renamed = []
site_enabled = False
default_site_disabled = False

def install(data):
    global site_enabled, default_site_disabled

    source_path = os.path.join(installation.root_dir, "installation", "templates", "site")
    target_path = os.path.join("/etc", "apache2", "sites-available", "critic-main")

    with open(target_path, "w") as target:
        created_file.append(target_path)

        os.chmod(target_path, 0640)

        with open(source_path, "r") as source:
            target.write((source.read().decode("utf-8") % data).encode("utf-8"))

    if installation.prereqs.a2enmod:
        process.check_call([installation.prereqs.a2enmod, "expires"])
        process.check_call([installation.prereqs.a2enmod, "rewrite"])
        process.check_call([installation.prereqs.a2enmod, "wsgi"])

    if installation.prereqs.a2ensite:
        process.check_call([installation.prereqs.a2ensite, "critic-main"])
        site_enabled = True
    if installation.prereqs.a2dissite:
        output = process.check_output([installation.prereqs.a2dissite, "default"], env={ "LANG": "C" })
        if "Site default disabled." in output:
            default_site_disabled = True

    process.check_call(["service", "apache2", "restart"])

    return True

def upgrade(arguments, data):
    source_path = os.path.join(installation.root_dir, "installation", "templates", "site")
    target_path = os.path.join("/etc", "apache2", "sites-available", "critic-main")
    backup_path = os.path.join(os.path.dirname(target_path), "_" + os.path.basename(target_path))

    source = open(source_path, "r").read().decode("utf-8") % data
    target = open(target_path, "r").read().decode("utf-8")

    if source != target:
        def generateVersion(label, path):
            if label == "updated":
                with open(path, "w") as target:
                    target.write(source.encode("utf-8"))

        update_query = installation.utils.UpdateModifiedFile(
            message="""\
The Apache site definition is about to be updated.  Please check that no local
modifications are being overwritten.

  Current version: %(current)s
  Updated version: %(updated)s

Please note that if the modifications are not installed, the system is
likely to break.
""",
            versions={ "current": target_path,
                       "updated": target_path + ".new" },
            options=[ ("i", "install the updated version"),
                      ("k", "keep the current version"),
                      ("d", ("current", "updated")) ],
            generateVersion=generateVersion)

        write_target = update_query.prompt() == "i"
    else:
        write_target = False

    if write_target:
        print "Updated file: %s" % target_path

        if not arguments.dry_run:
            os.rename(target_path, backup_path)
            renamed.append((target_path, backup_path))

            with open(target_path, "w") as target:
                created_file.append(target_path)
                os.chmod(target_path, 0640)
                target.write(source.encode("utf-8"))

    if write_target or installation.files.sources_modified or installation.config.modified_files:
        print
        print "Restarting Apache ..."

        if not arguments.dry_run:
            process.check_call(["service", "apache2", "restart"])

    return True

def undo():
    if site_enabled:
        process.check_call([installation.prereqs.a2dissite, "critic-main"])

        if default_site_disabled:
            process.check_call([installation.prereqs.a2ensite, "default"])

        if installation.prereqs.apache2ctl:
            process.check_call([installation.prereqs.apache2ctl, "restart"])

    map(os.unlink, created_file)

    for target, backup in renamed: os.rename(backup, target)

def finish():
    for target, backup in renamed: os.unlink(backup)
