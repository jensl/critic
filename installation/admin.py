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

system_recipients = None

def add_arguments(mode, parser):
    if mode != "install":
        return

    parser.add_argument("--admin-username", action="store",
                        help="name of Critic administrator user")
    parser.add_argument("--admin-email", action="store",
                        help="email address to Critic administrator user")
    parser.add_argument("--admin-fullname", action="store",
                        help="Critic administrator user's full name")
    parser.add_argument("--admin-password", action="store",
                        help="Critic administrator user's password")

def prepare(mode, arguments, data):
    global username, email, fullname, password

    if mode == "install":
        print """
Critic Installation: Administrator
==================================

An administrator user is a Critic user with some special privileges;
they can do various things using the Web interface that other users
are not allowed to do.  Additional administrator users can be added
post-installation using the 'criticctl' utility.

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

        print """
Critic Installation: System Messages
====================================

Critic sends out email notifications when unexpected errors (crashes)
occur, and in various other cases when things happen that the system
administrators might need to know about right away.
"""

        if arguments.system_recipients:
            system_recipients = arguments.system_recipients
        else:
            system_recipient = installation.input.string(
                prompt="Where should system messages be sent?",
                default="%s <%s>" % (fullname, email))
            system_recipients = [system_recipient]

        data["installation.admin.email"] = email
    else:
        import configuration

        try:
            system_recipients = configuration.base.SYSTEM_RECIPIENTS
        except AttributeError:
            system_recipients = ["%(fullname)s <%(email)s>" % admin
                                 for admin in configuration.base.ADMINISTRATORS]

        # The --system-recipients argument, on upgrade, is mostly intended to be
        # used by the testing framework.  It is checked after the code above has
        # run for testing purpose; making sure the code above ever runs while
        # testing is meaningful.
        if arguments.system_recipients:
            system_recipients = arguments.system_recipients

    data["installation.system.recipients"] = system_recipients

    return True

def install(data):
    global password

    try:
        criticctl_argv = [installation.criticctl.criticctl_path, "adduser",
                          "--name", username,
                          "--email", email,
                          "--fullname", fullname]
        if not password:
            criticctl_argv.extend(["--no-password"])
        else:
            criticctl_argv.extend(["--password", password])

        subprocess.check_output(criticctl_argv)

        for role in ["administrator", "repositories", "newswriter"]:
            subprocess.check_output(
                [installation.criticctl.criticctl_path, "addrole",
                 "--name", username,
                 "--role", role])
    except subprocess.CalledProcessError:
        return False

    return True
