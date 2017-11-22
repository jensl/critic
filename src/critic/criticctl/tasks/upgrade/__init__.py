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

import distutils.spawn
import json
import logging
import os
import signal
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

name = "upgrade"
description = "Upgrade Critic system."
allow_missing_configuration = True

from critic import api
from critic import background
from critic import base


SERIALIZE_LEGACY_CONFIGURATION_SCRIPT = """

import configuration, json, sys
data = {"errors": []}
for section_name in dir(configuration):
    section = getattr(configuration, section_name)
    if not isinstance(section, type(sys)):
        continue
    if not section.__name__.startswith("configuration."):
        continue
    for item_name in dir(section):
        if item_name.startswith("_") or item_name != item_name.upper():
            continue
        item = getattr(section, item_name)
        if isinstance(item, type(sys)):
            continue
        if callable(item):
            continue
        try:
            json.dumps(item)
        except TypeError as error:
            data["errors"].append({
                "section": section_name,
                "item": item_name,
                "error": str(error)
            })
            continue
        data[f"{section_name}.{item_name.lower()}"] = item
json.dump(data, sys.stdout)

"""


def serialize_legacy_configuration(arguments):
    from .. import fail

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(arguments.etc_dir, arguments.identity)
    try:
        legacy_configuration = json.loads(
            subprocess.check_output(
                [sys.executable, "-c", SERIALIZE_LEGACY_CONFIGURATION_SCRIPT], env=env
            )
        )
    except subprocess.CalledProcessError:
        fail("Failed to serialize legacy configuration!")
    return legacy_configuration


def import_legacy_configuration(arguments, legacy_configuration):
    def lazy():
        return {
            # Basic system details.
            "system.identity": legacy_configuration["base.system_identity"],
            "system.username": legacy_configuration["base.system_user_name"],
            "system.groupname": legacy_configuration["base.system_group_name"],
            # Database connection settings.
            "database.driver": legacy_configuration["database.driver"],
            "database.parameters": {
                "args": [],
                "kwargs": legacy_configuration["database.parameters"],
            },
            # System paths.
            "paths.home": arguments.home_dir,
            "paths.executables": os.path.dirname(sys.argv[0]),
            "paths.runtime": arguments.runtime_dir,
            "paths.logs": arguments.logs_dir,
            "paths.repositories": legacy_configuration["paths.git_dir"],
        }

    return lazy


def migration_name(module):
    _, _, name = module.__name__.rpartition(".")
    return name


def list_migrations():
    from . import migrations

    # Check that there are no duplicated indexes.
    indexes = set(module.index for module in migrations.modules)
    assert len(indexes) == len(migrations.modules)

    modules = sorted(migrations.modules, key=lambda module: module.index)
    return [(migration_name(module), module) for module in modules]


async def stop_services(critic):
    from .. import fail, install_systemd_service

    if critic is not None:
        # Check if we have a record of how the services are run:

        services_event = await api.systemevent.fetch(
            critic, category="install", key="services"
        )

        if services_event:
            if services_event.data["flavor"] == "systemd":
                install_systemd_service.stop_services(
                    services_event.data["service_name"]
                )
                return

    # Fall back to attempting to stop the services manually.

    servicemanager_pidfile = background.utils.service_pidfile("servicemanager")
    if not os.path.isfile(servicemanager_pidfile):
        logger.warning("%s: pidfile does not exist", servicemanager_pidfile)
        return False
    with open(servicemanager_pidfile, "r", encoding="utf-8") as file:
        servicemanager_pid = int(file.read().strip())

    try:
        os.kill(servicemanager_pid, 0)
    except OSError:
        logger.warning("%s: stale pidfile deleted", servicemanager_pidfile)
        os.unlink(servicemanager_pidfile)
        return False

    try:
        os.kill(servicemanager_pid, signal.SIGTERM)
    except OSError as error:
        fail("Failed to stop background services: %s", error)

    deadline = time.time() + 30
    while os.path.isfile(servicemanager_pidfile):
        if time.time() > deadline:
            fail("Timed out waiting for background services to stop!")
        time.sleep(0.1)

    return True


async def update_review_tags(critic):
    from critic import data
    from critic.api.transaction.review.updatereviewtags import UpdateReviewTags

    reviewtags = data.load_yaml("reviewtags.yaml")

    existing_tags = {}
    async with critic.query(
        """SELECT id, name, description
                 FROM reviewtags"""
    ) as result:
        async for reviewtag_id, name, description in result:
            existing_tags[name] = (reviewtag_id, description)

    logger.debug("existing_tags: %r", existing_tags)

    new_tags = []
    updated_tag_descriptions = []
    for reviewtag in reviewtags:
        try:
            reviewtag_id, description = existing_tags.pop(reviewtag["name"])
        except KeyError:
            new_tags.append(reviewtag)
        else:
            if description != reviewtag["description"]:
                updated_tag_descriptions.append(
                    {
                        "description": reviewtag["description"],
                        "reviewtag_id": reviewtag_id,
                    }
                )
    deleted_tag_ids = list(existing_tags.values())

    if new_tags or updated_tag_descriptions or deleted_tag_ids:
        async with critic.transaction() as cursor:
            if new_tags:
                await cursor.executemany(
                    """INSERT
                         INTO reviewtags (name, description)
                       VALUES ({name}, {description})""",
                    new_tags,
                )
            if updated_tag_descriptions:
                await cursor.executemany(
                    """UPDATE reviewtags
                          SET description={description}
                        WHERE id={reviewtag_id}""",
                    updated_tag_descriptions,
                )
            if deleted_tag_ids:
                await cursor.execute(
                    """DELETE
                         FROM reviewtags
                        WHERE {id=deleted_tag_ids:array}""",
                    deleted_tag_ids=deleted_tag_ids,
                )

    if new_tags:
        logger.info(
            "Added review tags: %s",
            ", ".join(reviewtag["name"] for reviewtag in new_tags),
        )

        reviews = await api.review.fetchAll(critic, state="open")

        async with api.transaction.start(critic) as transaction:
            for review in reviews:
                transaction.items.append(UpdateReviewTags(review))


async def upgrade(critic, configuration, arguments):
    from .. import as_user, fail

    try:
        migration_events = await api.systemevent.fetchAll(critic, category="migration")
    except api.DatabaseSchemaError:
        migration_events = []

    old_migrations = set(event.key for event in migration_events)
    new_migrations = [
        module for (name, module) in list_migrations() if name not in old_migrations
    ]

    if new_migrations:
        logger.debug("New migrations: ")
        for module in new_migrations:
            logger.debug("  - %s", migration_name(module))

        will_modify_database = any(
            ("database" in migration.scope) for migration in new_migrations
        )

        if will_modify_database and not hasattr(arguments, "dump_database"):
            fail(
                "Database will be modified. Please use --dump-database or "
                "--no-dump-database to indicate whether to take a database "
                "snapshot before continuing."
            )

        if arguments.dump_database:
            pg_dump = distutils.spawn.find_executable("pg_dump")
            if not pg_dump:
                fail("Could not find `pg_dump` executable in $PATH!")

            dump_dir = os.path.dirname(arguments.dump_database_file)
            if dump_dir and not os.path.isdir(dump_dir):
                try:
                    os.makedirs(dump_dir)
                except OSError as error:
                    fail("%s: failed to create directory: %s", dump_dir, error)

            with open(arguments.dump_database_file, "wb") as output_file:
                with as_user(name=configuration["system.username"]):
                    logger.info(
                        "Creating database snapshot: %s", arguments.dump_database_file
                    )
                    subprocess.check_call(
                        [pg_dump, "-Fc", "critic"], stdout=output_file
                    )

        for module in new_migrations:
            logger.info("Running migration: %s", os.path.basename(module.__file__))
            logger.info(" - %s", module.title)

            await module.perform(critic, arguments)

            async with api.transaction.start(critic) as transaction:
                transaction.addSystemEvent(
                    "migration",
                    migration_name(module),
                    module.title,
                    {"skipped": False},
                )

    await update_review_tags(critic)


def setup(parser):
    from .. import setup_filesystem_locations, setup_database_backup

    critic = parser.get_default("critic")

    if critic is None:
        system_group = parser.add_argument_group("System details")
        system_group.add_argument(
            "--identity", default="main", help="System identity to upgrade."
        )
        system_group.add_argument(
            "--etc-dir",
            default="/etc/critic",
            help="Directory containing legacy Critic configuration files.",
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
        "--database-host", help="Optional remote host running the database server."
    )
    database_group.add_argument(
        "--database-port", default=5432, type=int, help="Database server TCP port."
    )
    database_group.add_argument(
        "--database-wait",
        type=int,
        help=(
            "Wait at most this many seconds for the database "
            "host to start accepting connections."
        ),
    )
    database_group.add_argument(
        "--database-name", help="Name of database to connect to."
    )
    database_group.add_argument(
        "--database-username", help="Name of database user to connect as."
    )
    database_group.add_argument("--database-password", help="Database password.")
    database_group.set_defaults(database_driver="postgresql")

    setup_database_backup(parser)


async def main(critic, arguments):
    from .. import fail, as_user, install_systemd_service, ensure_system_user_and_group

    if not arguments.configuration:
        legacy_configuration = serialize_legacy_configuration(arguments)

        ensure_system_user_and_group(
            arguments,
            username=legacy_configuration["base.system_user_name"],
            groupname=legacy_configuration["base.system_group_name"],
            home_dir=legacy_configuration["paths.data_dir"],
        )

        base.configuration = import_legacy_configuration(
            arguments, legacy_configuration
        )

    configuration = base.configuration()

    # Override database connection parameters from our command line arguments.
    kwargs = configuration["database.parameters"]["kwargs"]
    if arguments.database_host is not None:
        kwargs["host"] = arguments.database_host
        kwargs["port"] = arguments.database_port
    if arguments.database_name:
        kwargs["dbname"] = arguments.database_name
    if arguments.database_username:
        kwargs["user"] = arguments.database_username
    if arguments.database_password:
        kwargs["password"] = arguments.database_password

    with as_user(name=configuration["system.username"]) as restore_user:
        session_started = False
        try:
            async with api.critic.startSession(for_system=True) as critic:
                session_started = True
                restore_user()

                stopped_services = False
                try:
                    if api.critic.settings():
                        stopped_services = await stop_services(critic)
                except api.critic.SessionNotInitialized:
                    pass

                await upgrade(critic, configuration, arguments)

                if stopped_services:
                    with as_user(name=configuration["system.username"]):
                        async with api.critic.startSession(for_system=True) as critic:
                            services_event = await api.systemevent.fetch(
                                critic, category="install", key="services"
                            )

                    if not services_event:
                        logger.warning(
                            "No services startup script installed; "
                            "services not restarted."
                        )
                        logger.info(
                            "You can run `%s run-task install:systemd-"
                            "service` to install a systemd service.",
                            sys.argv[0],
                        )
                    elif services_event.data["flavor"] == "systemd":
                        install_systemd_service.restart_service(
                            services_event.data["service_name"]
                        )

            logger.info("Upgrade finished.")
        except Exception:
            if session_started:
                raise
            fail("Could not connect to Critic's database!")
