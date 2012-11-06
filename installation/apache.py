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

pass_auth = "Off"

def prepare(arguments):
    global pass_auth

    if installation.config.auth_mode == "critic":
        pass_auth = "On"

    return True

created_file = []
site_enabled = False

def execute():
    source_path = os.path.join(installation.root_dir, "installation", "templates", "site")
    target_path = os.path.join("/etc", "apache2", "sites-available", "critic-main")

    with open(os.path.join(installation.root_dir, ".install.data")) as install_data:
        data = json.load(install_data)

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

    if installation.prereqs.apache2ctl:
        process.check_call([installation.prereqs.apache2ctl, "restart"])

    return True

def undo():
    if site_enabled:
        process.check_call([installation.prereqs.a2dissite, "critic-main"])

        if installation.prereqs.apache2ctl:
            process.check_call([installation.prereqs.apache2ctl, "restart"])

    map(os.unlink, created_file)
