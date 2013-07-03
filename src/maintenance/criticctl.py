# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
import argparse

import dbutils
import inpututils

db = dbutils.Database()

cursor = db.cursor()
cursor.execute("SELECT name FROM roles")

roles = [role for (role,) in cursor]

def valid_user(name):
    try:
        dbutils.User.fromName(db, name)
    except dbutils.NoSuchUser:
        return "no such user"

def valid_role(role):
    if role not in roles:
        return "invalid role; must be one of %s" % ", ".join(roles)

def invalid_user(name):
    try:
        dbutils.User.fromName(db, name)
        return "user exists"
    except dbutils.NoSuchUser:
        pass

def use_argument_or_ask(argument, prompt, check=None):
    if argument:
        if check:
            error = check(argument)
            if error:
                print "%s: %s" % (argument, error)
                sys.exit(-1)
        return argument
    else:
        return inpututils.string(prompt, check=check)

def listusers(argv):
    formats = {
        "tuples": {
            "pre": "# id, name, email, fullname, status\n[",
            "row": " (%r, %r, %r, %r, %r),",
            "post": "]",
        },
        "dicts":  {
            "pre": "[",
            "row": " {'id': %r, 'name': %r, 'email': %r, 'fullname': %r, 'status': %r},",
            "post": "]",
        },
        "table": {
            "pre": "  id |    name    |              email             |            fullname            | status\n" \
                   "-----+------------+--------------------------------+--------------------------------+--------",
            "row": "%4u | %10s | %30s | %-30s | %s",
            "post": "",
        },
    }

    parser = argparse.ArgumentParser(
        description="Critic administration interface: listusers",
        prog="criticctl [options] listusers")

    parser.add_argument("--format", "-f", choices=formats.keys(), default="table",
                        help='output format (defaults to "table")')

    arguments = parser.parse_args(argv)

    cursor.execute("""SELECT id, name, email, fullname, status FROM users ORDER BY id""")
    print formats[arguments.format]["pre"]
    for row in cursor:
        print formats[arguments.format]["row"] % row
    print formats[arguments.format]["post"]

def adduser(argv):
    import auth

    parser = argparse.ArgumentParser(
        description="Critic administration interface: adduser",
        prog="criticctl [options] adduser")

    parser.add_argument("--name", help="user name")
    parser.add_argument("--email", "-e", help="email address")
    parser.add_argument("--fullname", "-f", help="full name")
    parser.add_argument("--password", "-p", help="password")

    arguments = parser.parse_args(argv)

    name = use_argument_or_ask(arguments.name, "Username:", check=invalid_user)
    fullname = use_argument_or_ask(arguments.fullname, "Full name:")
    email = use_argument_or_ask(arguments.email, "Email address:")

    if arguments.password is None:
        password = inpututils.password("Password:")
    else:
        password = arguments.password

    dbutils.User.create(db, name, fullname, email, auth.hashPassword(password))

    db.commit()

    print "%s: user added" % name

def deluser(argv):
    import reviewing.utils

    parser = argparse.ArgumentParser(
        description="Critic administration interface: deluser",
        prog="criticctl [options] deluser")

    parser.add_argument("--name", help="user name")

    arguments = parser.parse_args(argv)

    name = use_argument_or_ask(arguments.name, "Username:", check=valid_user)

    reviewing.utils.retireUser(db, dbutils.User.fromName(db, name))

    db.commit()

    print "%s: user retired" % name

def role(command, argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: %s" % command,
        prog="criticctl [options] %s" % command)

    parser.add_argument("--name", help="user name")
    parser.add_argument("--role", choices=roles, help="role name")

    arguments = parser.parse_args(argv)

    name = use_argument_or_ask(arguments.name, "Username:", check=valid_user)
    role = use_argument_or_ask(arguments.role, "Role:", check=valid_role)

    user = dbutils.User.fromName(db, name)

    cursor.execute("""SELECT 1
                        FROM userroles
                       WHERE uid=%s
                         AND role=%s""",
                   (user.id, role))

    if command == "addrole":
        if cursor.fetchone():
            print "%s: user already has role '%s'" % (name, role)
        else:
            cursor.execute("""INSERT INTO userroles (uid, role)
                                   VALUES (%s, %s)""",
                           (user.id, role))
            db.commit()

            print "%s: role '%s' added" % (name, role)
    else:
        if not cursor.fetchone():
            print "%s: user doesn't have role '%s'" % (name, role)
        else:
            cursor.execute("""DELETE FROM userroles
                                    WHERE uid=%s
                                      AND role=%s""",
                           (user.id, role))

            db.commit()

            print "%s: role '%s' removed" % (name, role)

def main(parser, show_help, command, argv):
    returncode = 0

    if show_help or command is None:
        parser.print_help()
    else:
        if command == "listusers":
            listusers(argv)
            return
        elif command == "adduser":
            adduser(argv)
            return
        elif command == "deluser":
            deluser(argv)
            return
        elif command in ("addrole", "delrole"):
            role(command, argv)
            return
        else:
            print "ERROR: Invalid command: %s" % command
            returncode = 1

    print """
Available commands are:

  listusers List all users.
  adduser   Add a user.
  deluser   Retire a user.
  addrole   Add a role to a user.
  delrole   Remove a role from a user.

Use 'criticctl COMMAND --help' to see per command options."""

    return returncode
