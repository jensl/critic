# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import argparse
import distutils.spawn
import json
import logging
import os
import psycopg2
import re
import secrets
import stat
import struct
import subprocess
import sys
from psycopg2 import ProgrammingError, OperationalError

logger = logging.getLogger(__name__)

from critic import api
from critic import base

name = "install"
description = "Install the base Critic system."
allow_missing_configuration = True

SCHEMA_FILES = [
    # No dependencies.
    "dbschema/base.sql",
    "dbschema/users.sql",
    # Depends on: base[files].
    "dbschema/git.sql",
    # Depends on: users.
    "dbschema/news.sql",
    # Depends on: git, users.
    "dbschema/trackedbranches.sql",
    # Depends on: base[files], git.
    "dbschema/changesets.sql",
    # Depends on: base[files], git, users, changesets.
    "dbschema/reviews.sql",
    # Depends on: git, users, filters.
    "dbschema/preferences.sql",
    # Depends on: base[files], git, users, reviews.
    "dbschema/comments.sql",
    # Depends on: base[files], git, users, reviews.
    "dbschema/extensions.sql",
]


def get_hostname():
    from . import identify_os

    if identify_os() == "alpine":
        argv = ["hostname", "-f"]
    else:
        argv = ["hostname", "--fqdn"]
    try:
        return subprocess.check_output(argv, encoding="utf-8").strip()
    except subprocess.CalledProcessError:
        return None


PSQL_EXECUTABLE = None


def psql_argv(*, arguments=None, database=None):
    argv = [PSQL_EXECUTABLE, "-v", "ON_ERROR_STOP=1", "-w"]
    default_username = "postgres"
    if arguments is not None:
        if arguments.database_host:
            argv.extend(
                [
                    "-h",
                    arguments.database_host,
                    "-p",
                    str(arguments.database_port),
                    "-U",
                    arguments.database_username,
                ]
            )
            default_username = arguments.system_username
    if database is not None:
        argv.extend(["-d", database])
    return argv, default_username


def psql(command, *, database=None, arguments=None, username=None):
    from . import as_user

    argv, default_username = psql_argv(arguments=arguments, database=database)
    argv.extend(["-c", command])
    if username is None:
        username = default_username
    env = os.environ.copy()
    if arguments.database_password:
        env["PGPASSWORD"] = arguments.database_password
    logger.debug("running: %s [as %r]", " ".join(argv), username)
    with as_user(name=username):
        subprocess.check_output(argv, stderr=subprocess.STDOUT, env=env)


def psql_list_roles(arguments):
    from . import as_user

    argv, default_username = psql_argv(arguments=arguments)
    argv.extend(["--no-align", "--tuples-only", "-c", "SELECT rolname FROM pg_roles"])
    with as_user(name="postgres"):
        return subprocess.check_output(argv).decode().splitlines()


class SQLScript:
    def __init__(self, script_source):
        self.commands = []
        command = []
        quotes = []
        for line in script_source.splitlines():
            fragment, _, comment = line.strip().partition("--")
            fragment = fragment.strip()
            if not fragment:
                continue
            command.append(fragment)
            if fragment == "$$":
                if quotes and quotes[-1] == fragment:
                    quotes.pop()
                else:
                    quotes.append(fragment)
            if not quotes and fragment.endswith(";"):
                self.commands.append(" ".join(command))
                command = []


# Note: Imported and used in |upgrade/migrations/convert_from_legacy.py|.
def insert_systemsettings(connection, arguments, override_settings):
    from critic import data

    settings = {}

    def process(key_path, structure):
        assert isinstance(structure, dict), (key_path, structure)
        if "value" in structure and "description" in structure:
            assert key_path
            key = ".".join(key_path)
            assert key not in settings
            settings[key] = (
                structure["description"],
                structure["value"],
                structure.get("privileged", False),
            )
        else:
            for key, substructure in structure.items():
                process(key_path + [key], substructure)

    process([], data.load_yaml("systemsettings.yaml"))

    for key, override_value in override_settings.items():
        description, _, privileged = settings[key]
        settings[key] = (description, override_value, privileged)

    cursor = connection.cursor()
    cursor.executemany(
        """INSERT INTO systemsettings (key, description, value, privileged)
                VALUES (%s, %s, %s, %s)""",
        (
            (key, description, json.dumps(value), privileged)
            for key, (description, value, privileged) in settings.items()
        ),
    )


def sql_command_summary(command):
    match = re.match(
        r"^(CREATE (?:TABLE|(?:UNIQUE )?INDEX|TYPE|VIEW) \w+|ALTER TABLE \w+)", command
    )
    if match:
        return match.group(1)
    return command


def initialize_database(critic, arguments, connection):
    from critic import data
    from .upgrade import list_migrations

    cursor = connection.cursor()

    for script_filename in SCHEMA_FILES:
        script = SQLScript(data.load(script_filename))
        for command in script.commands:
            logger.debug(sql_command_summary(command))
            cursor.execute(command)
    logger.debug("Initialized database schema")

    cursor.execute(
        """INSERT
             INTO systemidentities (key, name, anonymous_scheme,
                                    authenticated_scheme, hostname,
                                    description, installed_sha1)
           VALUES (%s, %s, 'http', 'http', %s, 'N/A', 'N/A')""",
        (arguments.identity, arguments.identity, arguments.system_hostname),
    )

    logger.debug("Inserted system identity: %s", arguments.identity)

    override_settings = {"system.hostname": arguments.system_hostname}

    if arguments.flavor == "services":
        override_settings.update(
            {
                "services.gateway.enabled": arguments.flavor == "services",
                "services.gateway.secret": secrets.token_hex(),
            }
        )

    insert_systemsettings(connection, arguments, override_settings)

    logger.debug("Inserted system settings")

    preferences = data.load_json("preferences.json")

    for preference_name, preference_data in sorted(preferences.items()):
        relevance = preference_data.get("relevance", {})
        is_string = preference_data["type"] == "string"
        cursor.execute(
            """INSERT
                    INTO preferences (item, type, description, per_system,
                                    per_user, per_repository, per_filter)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                preference_name,
                preference_data["type"],
                preference_data["description"],
                relevance.get("system", True),
                relevance.get("user", True),
                relevance.get("repository", False),
                relevance.get("filter", False),
            ),
        )
        cursor.execute(
            """INSERT
                    INTO userpreferences (item, integer, string)
                VALUES (%s, %s, %s)""",
            (
                preference_name,
                int(preference_data["default"]) if not is_string else None,
                preference_data["default"] if is_string else None,
            ),
        )

    logger.debug("Inserted preferences")

    cursor.executemany(
        """INSERT
                INTO systemevents (category, key, title, data)
            VALUES (%s, %s, %s, %s)""",
        [
            ("migration", name, module.title, json.dumps({"skipped": True}))
            for name, module in list_migrations()
        ],
    )

    connection.commit()

    logger.debug("Inserted system events for skipped migrations")


async def ensure_database(critic, arguments, restore_user):
    from . import fail

    configuration = base.configuration()
    parameters = configuration["database.parameters"]

    connection = psycopg2.connect(*parameters["args"], **parameters["kwargs"])

    try:
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT TRUE FROM systemidentities LIMIT 1")
            cursor.fetchone()
        except (ProgrammingError, OperationalError):
            connection.rollback()
            empty_database = True
        else:
            empty_database = False

        if empty_database:
            initialize_database(critic, arguments, connection)

            logger.info("Initialized database")
        else:
            try:
                cursor.execute("SELECT TRUE FROM systemevents LIMIT 1")
                cursor.fetchone()
            except (ProgrammingError, OperationalError):
                connection.rollback()
                legacy_database = True
            else:
                legacy_database = False

            if legacy_database:
                fail(
                    "Legacy Critic system detected!",
                    "Please run `criticctl run-task upgrade` instead.",
                )
    finally:
        connection.close()

    from .upgrade import upgrade

    restore_user()
    await upgrade(critic, base.configuration(), arguments)


def setup(parser):
    from . import setup_filesystem_locations, setup_database_backup

    hostname = get_hostname()

    parser.add_argument(
        "--flavor",
        choices=("monolithic", "services", "auxiliary", "quickstart"),
        default="monolithic",
        help="Flavor of install.",
    )
    parser.add_argument("--is-testing", action="store_true", help=argparse.SUPPRESS)

    dependencies_group = parser.add_argument_group("Dependencies")
    dependencies_group.add_argument(
        "--install-postgresql",
        action="store_true",
        help="Install PostgreSQL client and server packages as required.",
    )

    system_group = parser.add_argument_group("System details")
    system_group.add_argument(
        "--identity", default="main", help="System identity to install."
    )
    system_group.add_argument(
        "--system-username", default="critic", help="System user to run Critic as."
    )
    system_group.add_argument(
        "--system-uid",
        help=(
            "User id to create system user with. Only used when a new system "
            "user is actually created."
        ),
    )
    system_group.add_argument(
        "--system-groupname", default="critic", help="System group to run Critic as."
    )
    system_group.add_argument(
        "--system-gid",
        help=(
            "Group id to create system group with. Only used when a new "
            "system group is actually created."
        ),
    )
    system_group.add_argument(
        "--system-hostname", default=hostname, help="Fully qualified system hostname."
    )

    services_group = parser.add_argument_group("Critic services")
    services_group.add_argument(
        "--services-host", help="Name of host running Critic's services."
    )
    services_group.add_argument(
        "--services-port",
        type=int,
        default=9987,
        help="TCP port that gateway service listens at.",
    )
    services_group.add_argument(
        "--services-wait",
        type=int,
        help=(
            "Wait at most this many seconds for the gateway service to start "
            "accepting connections."
        ),
    )

    setup_filesystem_locations(parser)

    database_group = parser.add_argument_group(
        "Database settings",
        description=(
            "By default, Critic sets up a database in a PostgreSQL "
            "running on the local machine. By specifying a database "
            "server hostname, the system can be configured to use a "
            "database server running on a different machine instead. "
            "In that case, the database needs to have been created "
            "already; this script can not do that."
        ),
    )
    database_group.add_argument(
        "--database-driver",
        choices=("postgresql", "sqlite"),
        default="postgresql",
        help="Type of database to install.",
    )
    database_group.add_argument(
        "--database-path", help="[sqlite] Path of database file."
    )
    database_group.add_argument(
        "--database-host",
        help="[postgresql] Optional remote host running the database server.",
    )
    database_group.add_argument(
        "--database-port",
        default=5432,
        type=int,
        help="[postgresql] Database server TCP port.",
    )
    database_group.add_argument(
        "--database-wait",
        type=int,
        help=(
            "[postgresql] Wait at most this many seconds for the database "
            "host to start accepting connections."
        ),
    )
    database_group.add_argument(
        "--database-name",
        default="critic",
        help="[postgresql] Name of database to create/connect to.",
    )
    database_group.add_argument(
        "--database-username",
        default="critic",
        help="[postgresql] Name of database user to create/connect as.",
    )
    database_group.add_argument(
        "--database-password", help="[postgresql] Database password."
    )
    database_group.add_argument(
        "--no-create-database",
        action="store_true",
        help="[postgresql] Assume that the named database exists already.",
    )
    database_group.add_argument(
        "--recreate-database",
        action="store_true",
        help="[postgresql] Drop the named database first if it exists already.",
    )
    database_group.add_argument(
        "--no-create-database-user",
        action="store_true",
        help=(
            "[postgresql] Assume that the named database user exists already "
            "and has the required access to the named database."
        ),
    )

    # We may run migrations, so add arguments for controlling whether to
    # generate a database snapshot before doing so. The arguments are optional
    # unless a migration will run that modifies the database.
    setup_database_backup(parser)

    parser.set_defaults(run_as_root=True)


def ensure_postgresql(arguments):
    from . import InvalidUser, fail, install

    global PSQL_EXECUTABLE

    PSQL_EXECUTABLE = distutils.spawn.find_executable("psql")
    if not PSQL_EXECUTABLE:
        if not arguments.install_postgresql:
            fail(
                "Could not find `psql` executable in $PATH!",
                "Rerun with --install-postgresql to attempt to install "
                "required packages automatically, or otherwise make sure it "
                "is available and rerun this command.",
            )
        install("postgresql-client")
        PSQL_EXECUTABLE = distutils.spawn.find_executable("psql")
        if not PSQL_EXECUTABLE:
            fail("Still could not find `psql` executable in $PATH!")

    try:
        psql("SELECT 1", arguments=arguments)
    except (subprocess.CalledProcessError, InvalidUser):
        if arguments.database_host:
            fail(
                "Could not connect to PostgreSQL database at %s:%d!"
                % (arguments.database_host, arguments.database_port),
                "Please ensure that it is running and that the connection "
                "details provided are correct.",
            )
        if not arguments.install_postgresql:
            fail(
                "Could not connect to local PostgreSQL database!",
                "Rerun with --install-postgresql to attempt to install "
                "required packages automatically, or otherwise make sure it "
                "is available and rerun this command.",
            )
        install("postgresql")
        try:
            psql("SELECT 1", arguments=arguments)
        except subprocess.CalledProcessError:
            fail("Still could not connect!")


def setup_postgresql_database(arguments):
    from . import fail, wait_for_connection

    kwargs = {"dbname": arguments.database_name, "user": arguments.database_username}

    if arguments.database_password:
        kwargs["password"] = arguments.database_password

    if arguments.database_host:
        kwargs.update(
            {"host": arguments.database_host, "port": arguments.database_port}
        )

        # A minimal conversation with the PostgreSQL server. This prevents it
        # from logging our (successful) connection attempt as invalid.
        protocol_version = struct.pack("!i", 196608)
        startup_content = (
            protocol_version
            + b"user\0"
            + arguments.database_username.encode()
            + b"\0\0"
        )
        startup_message = struct.pack("!i", 4 + len(startup_content)) + startup_content
        terminate_message = struct.pack("!ci", b"X", 4)
        payload = startup_message + terminate_message

        if not wait_for_connection(
            arguments.database_host,
            arguments.database_port,
            arguments.database_wait,
            payload=payload,
        ):
            fail(
                "Failed to connect to PostgreSQL at %s:%d!"
                % (arguments.database_host, arguments.database_port)
            )
    else:
        if arguments.system_username != arguments.database_username:
            if not arguments.database_password:
                logger.warning(
                    "System username and database username differ; a database "
                    "password is probably required for authentication to work."
                )

        if not arguments.no_create_database:
            try:
                psql("SELECT 1", database=arguments.database_name, arguments=arguments)
            except subprocess.CalledProcessError:
                pass
            else:
                if arguments.recreate_database:
                    psql(
                        f'DROP DATABASE "{arguments.database_name}"',
                        arguments=arguments,
                    )
                else:
                    fail("The database %r already exists!" % arguments.database_name)

            psql(f'CREATE DATABASE "{arguments.database_name}"', arguments=arguments)
            psql(
                f'CREATE EXTENSION IF NOT EXISTS "plpgsql"',
                database=arguments.database_name,
                arguments=arguments,
            )

        try:
            psql("SELECT 1", database=arguments.database_name, arguments=arguments)
        except subprocess.CalledProcessError:
            fail("Failed to connect to database %r!" % arguments.database_name)

        if not arguments.no_create_database_user:
            if arguments.database_username in psql_list_roles(arguments):
                logger.info(
                    "The database user %r already exists." % arguments.database_username
                )
            else:
                create_role = (
                    f'CREATE USER "{arguments.database_username}" ' "WITH LOGIN"
                )
                if arguments.database_password:
                    create_role += f" PASSWORD '{arguments.database_password}'"
                psql(create_role, arguments=arguments)

            psql(
                f'GRANT ALL ON DATABASE "{arguments.database_name}" '
                f'TO "{arguments.database_username}"',
                arguments=arguments,
            )

        try:
            psql(
                "SELECT 1",
                database=arguments.database_name,
                username=arguments.database_username,
                arguments=arguments,
            )
        except subprocess.CalledProcessError:
            fail(
                "Failed to connect to database %r as user %r!",
                arguments.database_name,
                arguments.database_username,
            )

    return {"args": [], "kwargs": kwargs}


def setup_sqlite_database(arguments):
    return {"args": [arguments.database_path], "kwargs": {}}


async def main(critic, arguments):
    from . import (
        fail,
        as_user,
        wait_for_connection,
        ensure_dir,
        ensure_system_user_and_group,
        write_configuration,
    )

    if arguments.flavor in ("monolithic", "services", "quickstart"):
        if arguments.database_driver == "postgresql" and not arguments.database_host:
            ensure_postgresql(arguments)

        if arguments.system_hostname is None:
            fail("Must specify --system-hostname with --flavor=%s!" % arguments.flavor)
    elif not arguments.database_host:
        fail("Must specify --database-host with --flavor=%s!" % arguments.flavor)

    if arguments.database_driver == "sqlite" and arguments.flavor != "quickstart":
        fail("Must specify --flavor=quickstart with --database-driver=sqlite!")

    system_uid, system_gid = ensure_system_user_and_group(
        arguments,
        username=arguments.system_username,
        force_uid=arguments.system_uid,
        groupname=arguments.system_groupname,
        force_gid=arguments.system_gid,
        home_dir=arguments.home_dir,
    )

    if arguments.database_driver == "postgresql":
        database_parameters = setup_postgresql_database(arguments)
    else:
        database_parameters = setup_sqlite_database(arguments)

    def resolve(path):
        return path.format(identity=arguments.identity)

    ensure_dir(base.settings_dir(), uid=system_uid, gid=system_gid)

    arguments.home_dir = resolve(arguments.home_dir)
    arguments.runtime_dir = resolve(arguments.runtime_dir)
    arguments.logs_dir = resolve(arguments.logs_dir)

    ensure_dir(arguments.home_dir, uid=system_uid, gid=system_gid)
    ensure_dir(
        arguments.runtime_dir,
        uid=system_uid,
        gid=system_gid,
        sub_directories=["sockets"],
    )
    ensure_dir(arguments.logs_dir, uid=system_uid, gid=system_gid)

    if arguments.flavor in ("monolithic", "services", "quickstart"):
        arguments.repositories_dir = resolve(arguments.repositories_dir)
        ensure_dir(arguments.repositories_dir, uid=system_uid, gid=system_gid)

    logger.debug(f"{sys.argv[0]=}")

    configuration = {
        # Basic system details.
        "system.identity": arguments.identity,
        "system.username": arguments.system_username,
        "system.groupname": arguments.system_groupname,
        "system.flavor": arguments.flavor,
        # Database connection settings.
        "database.driver": arguments.database_driver,
        "database.parameters": database_parameters,
        # System paths.
        "paths.home": arguments.home_dir,
        "paths.executables": os.path.dirname(sys.argv[0]),
        "paths.runtime": arguments.runtime_dir,
        "paths.logs": arguments.logs_dir,
    }

    if arguments.flavor in ("monolithic", "services", "quickstart"):
        configuration.update(
            {
                # File-system path to Git repositories.
                "paths.repositories": arguments.repositories_dir,
                # File-system path to persistent Critic data.
                "paths.data": arguments.data_dir,
                # File-system path to temporary Critic data.
                "paths.scratch": arguments.scratch_dir,
            }
        )

    if arguments.services_host:
        configuration.update(
            {
                # Specifies how to connect to services via the gateway service.
                "services.host": arguments.services_host,
                "services.port": arguments.services_port,
            }
        )

        if not wait_for_connection(
            arguments.services_host, arguments.services_port, arguments.services_wait
        ):
            fail(
                "Failed to connect to Critic services at %s:%d!"
                % (arguments.services_host, arguments.services_port)
            )

    if arguments.flavor == "quickstart":
        configuration["system.is_quickstarted"] = True

    if arguments.is_testing:
        configuration["system.is_testing"] = True

    write_configuration(configuration)

    if arguments.flavor in ("monolithic", "services", "quickstart"):
        with as_user(uid=system_uid) as restore_user:
            async with api.critic.startSession(for_system=True) as critic:
                await ensure_database(critic, arguments, restore_user)

        # Update ownership and modes on all repository directories and files. We
        # might have created the user/group that should own them above, so it's
        # not really feasible to assume the files are owned by them already.
        #
        # This is primarily relevant when running containerized, in which case
        # the repository storage is persistent but this script re-installs the
        # system every time the container is recreated. For a traditional
        # monolithic install, there would be no directories at this point, and
        # this code does nothing.
        in_repository = False
        for dirpath, dirnames, filenames in os.walk(arguments.repositories_dir):
            logger.debug("Directory: %s", dirpath)
            if in_repository and not dirpath.startswith(in_repository + "/"):
                in_repository = False
            if (
                not in_repository
                and dirpath.endswith(".git")
                and "config" in filenames
                and "refs" in dirnames
                and "objects" in dirnames
            ):
                in_repository = dirpath
            if in_repository:
                # Directory that is part of repository: drwxrws---
                dirmode = 0o770 | stat.S_ISGID
                # File that is part of repository: -rw-rw----
                filemode = 0o660
            else:
                # Other directory: drwxr-x---
                dirmode = 0o750
                # Other file: -rw-r-----
                filemode = 0o640
            os.chown(dirpath, system_uid, system_gid)
            os.chmod(dirpath, dirmode)
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.islink(filepath):
                    # Ignore symbolic links.
                    continue
                os.chown(filepath, system_uid, system_gid)
                os.chmod(filepath, filemode)
    else:
        # FIXME: Check that database contains record of all migrations, to
        # ensure that running code is compatible with database state.
        pass
