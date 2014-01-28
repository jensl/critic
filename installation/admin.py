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

import subprocess

import installation

username = None
email = None
fullname = None
password = None

def prepare(mode, arguments, data):
    global username, email, fullname, password

    if mode == "install":
        print """
Critic Installation: Administrator
==================================

The administrator user receives email notifications about unexpected
errors that occur.  He/she can also do various things using the Web
interface that most users are not allowed to do.

This user does not need to match a system user on this machine.
"""

        if arguments.admin_username: username = arguments.admin_username
        else: username = installation.input.string(prompt="Administrator user name:")

        if arguments.admin_email: email = arguments.admin_email
        else: email = installation.input.string(prompt="Administrator email address:")

        if arguments.admin_fullname: fullname = arguments.admin_fullname
        else: fullname = installation.input.string(prompt="Administrator full name:")

        if installation.config.auth_mode == "critic":
            if arguments.admin_password: password = arguments.admin_password
            else: password = installation.input.password("Password for '%s':" % username)
    else:
        import configuration

        admin = configuration.base.ADMINISTRATORS[0]

        username = admin["name"]
        email = admin["email"]
        fullname = admin["fullname"]

    data["installation.admin.username"] = username
    data["installation.admin.email"] = email
    data["installation.admin.fullname"] = fullname

    return True

def install(data):
    global password

    try:
        subprocess.check_output(
            [installation.criticctl.criticctl_path, "adduser",
             "--name", username,
             "--email", email,
             "--fullname", fullname,
             "--password", password])

        for role in ["administrator", "repositories", "newswriter"]:
            subprocess.check_output(
                [installation.criticctl.criticctl_path, "addrole",
                 "--name", username,
                 "--role", role])
    except subprocess.CalledProcessError:
        return False

    return True
