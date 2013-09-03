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

import sys
import subprocess
import os

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

    import psycopg2

    def adapt(value):
        return psycopg2.extensions.adapt(value).getquoted()

    if password is not None:
        try:
            import auth
        except ImportError:
            password = installation.process.check_input(
                [sys.executable, "-c",
                 "import sys, auth; sys.stdout.write(auth.hashPassword(sys.stdin.read()))"],
                stdin=password, stdout=subprocess.PIPE,
                env={ "PYTHONPATH": ":".join([os.path.join(installation.paths.etc_dir, "main"),
                                              installation.paths.install_dir]) })
        else:
            password = auth.hashPassword(password)

    installation.process.check_input(
        ["su", "-s", "/bin/sh", "-c", "psql -q -v ON_ERROR_STOP=1 -f -", installation.system.username],
        stdin=("""INSERT INTO users (name, email, password, fullname, status)
                       VALUES (%s, %s, %s, %s, 'current');"""
               % (adapt(username),
                  adapt(email),
                  adapt(password),
                  adapt(fullname))))

    installation.process.check_input(
        ["su", "-s", "/bin/sh", "-c", "psql -q -v ON_ERROR_STOP=1 -f -", installation.system.username],
        stdin=("""INSERT INTO userroles (uid, role)
                       SELECT id, 'administrator'
                         FROM users
                        WHERE name=%s;"""
               % adapt(username)))

    installation.process.check_input(
        ["su", "-s", "/bin/sh", "-c", "psql -q -v ON_ERROR_STOP=1 -f -", installation.system.username],
        stdin=("""INSERT INTO userroles (uid, role)
                       SELECT id, 'repositories'
                         FROM users
                        WHERE name=%s;"""
               % adapt(username)))

    return True
