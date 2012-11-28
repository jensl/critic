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

import pwd
import grp

import installation
from installation import process

hostname = None
username = "critic"
email = None
uid = None

groupname = "critic"
gid = None

create_system_user = None
created_system_user = False
create_system_group = None
created_system_group = False

def prepare(mode, arguments, data):
    global hostname, username, email, create_system_user
    global groupname, create_system_group
    global uid, gid

    if mode == "install":
        print """
Critic Installation: System
===========================
"""

        if arguments.system_hostname: hostname = arguments.system_hostname
        else:
            try: hostname = process.check_output(["hostname", "--fqdn"]).strip()
            except: pass

            hostname = installation.input.string(prompt="What is the machine's FQDN?",
                                                        default=hostname)

        while True:
            if arguments.system_username: username = arguments.system_username
            else:
                username = installation.input.string(prompt="What system user should Critic run as?",
                                                            default=username)

            try:
                pwd.getpwnam(username)
                user_exists = True
            except:
                user_exists = False

            if user_exists:
                print """
The system user '%s' already exists.
""" % username

                if installation.input.yes_or_no(prompt="Use the existing system user '%s'?" % username,
                                                default=True):
                    create_system_user = False
                    break
            else:
                print """
The system user '%s' doesn't exists.
""" % username

                if arguments.force_create_system_user or installation.input.yes_or_no(prompt="Create a system user named '%s'?" % username,
                                                default=True):
                    create_system_user = True
                    break

        while True:
            if arguments.system_groupname: groupname = arguments.system_groupname
            else:
                groupname = installation.input.string(prompt="What system group should Critic run as?",
                                                            default=groupname)

            try:
                grp.getgrnam(groupname)
                group_exists = True
            except:
                group_exists = False

            if group_exists:
                print """
The system group '%s' already exists.
""" % groupname

                if installation.input.yes_or_no(prompt="Use the existing system group '%s'?" % groupname,
                                                default=True):
                    create_system_group = False
                    break
            else:
                print """
The system group '%s' doesn't exists.
""" % groupname

                if arguments.force_create_system_group or installation.input.yes_or_no(prompt="Create a system group named '%s'?" % groupname,
                                                default=True):
                    create_system_group = True
                    break

        if arguments.system_email: email = arguments.system_email
        else:
            email = installation.input.string(prompt="What address should be used as the sender of emails from the system?",
                                              default=("%s@%s" % (username, hostname)))
    else:
        import configuration

        hostname = configuration.base.HOSTNAME
        username = configuration.base.SYSTEM_USER_NAME
        email = configuration.base.SYSTEM_USER_EMAIL

        try: groupname = configuration.base.SYSTEM_GROUP_NAME
        except AttributeError: groupname = data["installation.system.groupname"]

        uid = pwd.getpwnam(username).pw_uid
        gid = grp.getgrnam(groupname).gr_gid

    data["installation.system.hostname"] = hostname
    data["installation.system.username"] = username
    data["installation.system.email"] = email
    data["installation.system.groupname"] = groupname

    return True

def install(data):
    global uid, gid

    if create_system_group:
        print "Creating group '%s' ..." % groupname

        process.check_call(["addgroup", "--quiet", "--system", groupname])

    if create_system_user:
        print "Creating user '%s' ..." % username

        process.check_call(["adduser", "--quiet", "--system", "--ingroup=%s" % groupname, "--home=%s" % installation.paths.data_dir, "--disabled-login", username])

    uid = pwd.getpwnam(username).pw_uid
    gid = grp.getgrnam(groupname).gr_gid

    return True

def undo():
    if created_system_user:
        print "Deleting user '%s' ..." % username

        process.check_call(["deluser", "--system", username])

    if created_system_group:
        print "Deleting group '%s' ..." % groupname

        process.check_call(["delgroup", "--system", groupname])
