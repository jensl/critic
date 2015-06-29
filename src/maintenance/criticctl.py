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

import auth
import configuration
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

def check_argument(argument, check):
    if argument and check:
        error = check(argument)
        if error:
            print >>sys.stderr, "%s: %s" % (argument, error)
            sys.exit(-1)

def use_argument_or_ask(argument, prompt, check=None):
    if argument:
        check_argument(argument, check)
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

    cursor.execute("""SELECT users.id, name, useremails.email, fullname, status
                        FROM users
             LEFT OUTER JOIN useremails ON (useremails.id=users.email)
                    ORDER BY users.id""")

    print formats[arguments.format]["pre"]
    for row in cursor:
        print formats[arguments.format]["row"] % row
    print formats[arguments.format]["post"]

def adduser(argv):
    class NoEmail:
        pass
    class NoPassword:
        pass

    parser = argparse.ArgumentParser(
        description="Critic administration interface: adduser",
        prog="criticctl [options] adduser")

    parser.add_argument("--name", help="user name")
    parser.add_argument("--email", "-e", help="email address")
    parser.add_argument("--no-email", dest="email", action="store_const",
                        const=NoEmail, help="create user without email address")
    parser.add_argument("--fullname", "-f", help="full name")
    parser.add_argument("--password", "-p", help="password")
    parser.add_argument("--no-password", dest="password", action="store_const",
                        const=NoPassword, help="create user without password")

    arguments = parser.parse_args(argv)

    name = use_argument_or_ask(arguments.name, "Username:", check=invalid_user)
    fullname = use_argument_or_ask(arguments.fullname, "Full name:")

    if arguments.email is NoEmail:
        email = None
    else:
        email = use_argument_or_ask(arguments.email, "Email address:")
        if not email.strip():
            email = None

    if arguments.password is NoPassword:
        hashed_password = None
    else:
        if arguments.password is None:
            password = inpututils.password("Password:")
        else:
            password = arguments.password
        hashed_password = auth.hashPassword(password)

    dbutils.User.create(db, name, fullname, email, email_verified=None,
                        password=hashed_password)

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

def passwd(argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: passwd",
        prog="criticctl [options] passwd")

    class NoPassword:
        pass

    parser.add_argument("--name", help="user name")
    parser.add_argument("--password", help="password")
    parser.add_argument("--no-password", dest="password", action="store_const",
                        const=NoPassword, help="delete the user's password")

    arguments = parser.parse_args(argv)

    name = use_argument_or_ask(arguments.name, "Username:", check=valid_user)

    if arguments.password is NoPassword:
        hashed_password = None
    else:
        if arguments.password is None:
            password = inpututils.password("Password:")
        else:
            password = arguments.password
        hashed_password = auth.hashPassword(password)

    cursor.execute("""UPDATE users
                         SET password=%s
                       WHERE name=%s""",
                   (hashed_password, name))

    db.commit()

    if hashed_password:
        print "%s: password changed" % name
    else:
        print "%s: password deleted" % name

def connect(command, argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: %s" % command,
        prog="criticctl [options] %s" % command)

    providers = sorted(provider_name for provider_name, provider
                       in configuration.auth.PROVIDERS.items()
                       if command == "disconnect" or provider.get("enabled"))

    if len(providers) == 0:
        print >>sys.stderr, "No external authentication providers configured!"
        return 1

    parser.add_argument("--name", help="user name")
    parser.add_argument("--provider", choices=providers,
                        help="external authentication provider name")

    if command == "connect":
        parser.add_argument("--account", help="external account identifier")

    arguments = parser.parse_args(argv)

    def valid_provider(provider):
        if provider not in providers:
            return ("invalid authentication provider; must be one of %s"
                    % ", ".join(providers))

    name = use_argument_or_ask(arguments.name, "Username:", check=valid_user)

    if len(providers) == 1:
        check_argument(arguments.provider, check=valid_provider)
        provider = providers[0]
    else:
        provider = use_argument_or_ask(
            arguments.provider, "Authentication provider:", check=valid_provider)

    user = dbutils.User.fromName(db, name)
    provider = auth.PROVIDERS[provider]

    if command == "connect":
        cursor.execute("""SELECT 1
                            FROM externalusers
                           WHERE uid=%s
                             AND provider=%s""",
                       (user.id, provider.name))

        if cursor.fetchone():
            print >>sys.stderr, ("%s: user already connected to a %s"
                                 % (user.name, provider.getTitle()))
            return 1

        account = use_argument_or_ask(
            arguments.account, provider.getAccountIdDescription() + ":")

        cursor.execute("""SELECT id, uid
                            FROM externalusers
                           WHERE provider=%s
                             AND account=%s""",
                       (provider.name, account))

        row = cursor.fetchone()

        if row:
            external_id, user_id = row

            if user_id is not None:
                user = dbutils.User.fromId(db, user_id)

                print >>sys.stderr, ("%s %r: already connected to local user %s"
                                     % (provider.getTitle(), account, user.name))
                return 1

            cursor.execute("""UPDATE externalusers
                                 SET uid=%s
                               WHERE id=%s""",
                           (user.id, external_id))
        else:
            cursor.execute("""INSERT INTO externalusers (uid, provider, account)
                                   VALUES (%s, %s, %s)""",
                           (user.id, provider.name, account))

        print "%s: connected to %s %r" % (name, provider.getTitle(), account)
    else:
        cursor.execute("""SELECT account
                            FROM externalusers
                           WHERE uid=%s
                             AND provider=%s""",
                       (user.id, provider.name))

        row = cursor.fetchone()

        if not row:
            print >>sys.stderr, ("%s: user not connected to a %s"
                                 % (name, provider.getTitle()))
            return 1

        account, = row

        cursor.execute("""DELETE FROM externalusers
                                WHERE uid=%s
                                  AND provider=%s""",
                       (user.id, provider.name))

        print ("%s: disconnected from %s %r"
               % (name, provider.getTitle(), account))

    db.commit()

    return 0

def configtest(command, argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: configtest",
        prog="criticctl [options] configtest")

    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress non-error/warning output")

    arguments = parser.parse_args(argv)

    import maintenance.configtest

    errors, warnings = maintenance.configtest.testConfiguration()

    def printIssue(issue):
        print str(issue)
        print

    for error in errors:
        printIssue(error)
    for warning in warnings:
        printIssue(warning)

    if not errors:
        if not arguments.quiet:
            print "System configuration valid."
        return 0
    else:
        return 1

def restart(command, argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: restart",
        prog="criticctl [options] restart")

    parser.parse_args(argv)

    result = configtest("configtest", ["--quiet"])

    if result != 0:
        print >>sys.stderr, "ERROR: System configuration is not valid."
        return result

    import os
    import subprocess

    system_identity = configuration.base.SYSTEM_IDENTITY

    try:
        os.seteuid(0)
        os.setegid(0)
    except OSError:
        print >>sys.stderr, "ERROR: 'criticctl restart' must be run as root."
        return 1

    if configuration.base.WEB_SERVER_INTEGRATION == "apache":
        web_server_service = "apache2"
    elif configuration.base.WEB_SERVER_INTEGRATION in ("nginx+uwsgi", "uwsgi"):
        web_server_service = "uwsgi"
    else:
        web_server_service = None

    if web_server_service:
        subprocess.check_call(["service", web_server_service, "stop"])
    subprocess.check_call(["service", "critic-" + system_identity, "restart"])
    if web_server_service:
        subprocess.check_call(["service", web_server_service, "start"])

    return 0

def stop(command, argv):
    parser = argparse.ArgumentParser(
        description="Critic administration interface: stop",
        prog="criticctl [options] stop")

    parser.parse_args(argv)

    import os
    import subprocess

    system_identity = configuration.base.SYSTEM_IDENTITY

    try:
        os.seteuid(0)
        os.setegid(0)
    except OSError:
        print >>sys.stderr, "ERROR: 'criticctl stop' must be run as root."
        return 1

    if configuration.base.WEB_SERVER_INTEGRATION == "apache":
        web_server_service = "apache2"
    elif configuration.base.WEB_SERVER_INTEGRATION in ("nginx+uwsgi", "uwsgi"):
        web_server_service = "uwsgi"
    else:
        web_server_service = None

    if web_server_service:
        subprocess.check_call(["service", web_server_service, "stop"])
    subprocess.check_call(["service", "critic-" + system_identity, "stop"])

    return 0

def main(parser, show_help, command, argv):
    returncode = 0

    if show_help or command is None:
        parser.print_help()
    else:
        if command == "listusers":
            listusers(argv)
            return 0
        elif command == "adduser":
            adduser(argv)
            return 0
        elif command == "deluser":
            deluser(argv)
            return 0
        elif command in ("addrole", "delrole"):
            role(command, argv)
            return 0
        elif command == "passwd":
            passwd(argv)
            return 0
        elif command in ("connect", "disconnect"):
            return connect(command, argv)
        elif command == "configtest":
            return configtest(command, argv)
        elif command == "restart":
            return restart(command, argv)
        elif command == "stop":
            return stop(command, argv)
        else:
            print >>sys.stderr, "ERROR: Invalid command: %s" % command
            returncode = 1

    print """
Available commands are:

  listusers List all users.
  adduser   Add a user.
  deluser   Retire a user.
  addrole   Add a role to a user.
  delrole   Remove a role from a user.
  passwd    Set or delete a user's password.

  connect    Set up connection between user and external authentication
             provider.
  disconnect Remove such connection.

  configtest Test system configuration.
  restart    Restart host WSGI container and Critic's background services.
  stop       Stop host WSGI container and Critic's background services.

Use 'criticctl COMMAND --help' to see per command options."""

    return returncode
