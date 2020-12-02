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
import json
import logging
import multiprocessing
import os
import sys

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from .utils import fail
from .systemctl import check, start_service, restart_service, daemon_reload

TCP_ARGUMENTS = """\
  --host=%(host)s \\
  --port=%(port)d
"""

UNIX_ARGUMENTS = """\
  --unix=%(sockets_dir)s/aiohttp_container.unix \\
  --unix-socket-owner=%(httpd_username)s:%(httpd_groupname)s
"""

TEMPLATE = """

[Unit]
Description=Critic code review system: application container
Requires=%(requires)s
After=%(after)s

[Service]
ExecStart=%(criticctl_path)s run-frontend \\
  --flavor=aiohttp \\
  --lb-frontend=builtin \\
  --lb-backends=%(processes)s \\
%(listen_arguments)s
KillMode=mixed

[Install]
WantedBy=multi-user.target

"""

name = "container:aiohttp"
description = """\
Install a systemd service that runs an aiohttp-based application container.

This container speaks HTTP, so can in theory be used as an HTTP front-end as
well, but this is not a recommended configuration for production use. It does
not support HTTPS."""


def sockets_dir():
    return os.path.join(base.configuration()["paths.runtime"], "sockets")


def setup(parser: argparse.ArgumentParser) -> None:
    identity = parser.get_default("configuration")["system.identity"]

    service_group = parser.add_argument_group("Systemd service options")
    service_group.add_argument(
        "--service-file",
        default=f"/etc/systemd/system/critic-{identity}-container.service",
        help="Service file to create.",
    )
    service_group.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing service file instead of aborting.",
    )
    service_group.add_argument(
        "--start-service",
        action="store_true",
        help="Start the service after creating the service file.",
    )

    httpd_group = parser.add_argument_group("HTTP front-end user details")
    httpd_group.add_argument(
        "--httpd-user", default="www-data", help="User that front-end runs as."
    )
    httpd_group.add_argument(
        "--httpd-group", default="www-data", help="Group that front-end runs as."
    )

    backend_group = parser.add_argument_group(
        title="Backend options",
        description=(
            "By default, the backend listens at localhost:8080, "
            "meaning it does not accept connections from other "
            "computers. This makes sense assuming another HTTP server "
            "is running on the system, acting as a reverse proxy, "
            "which is the recommended configuration.\n\n"
            "Use --host=* to listen at all local interfaces, or "
            "--unix to listen on a UNIX socket instead."
        ),
    )
    backend_group.add_argument(
        "--host",
        default="localhost",
        help="Interface at which to listen for connections.",
    )
    backend_group.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port at which to listen for connections.",
    )
    backend_group.add_argument(
        "--unix",
        action="store_true",
        help=(
            "Listen for connections on a UNIX socket instead of a TCP "
            "socket. The socket is created in " + sockets_dir()
        ),
    )
    backend_group.add_argument(
        "--processes",
        type=int,
        default=multiprocessing.cpu_count(),
        help=(
            "Number of backend processes to run. Each process can handle "
            "multiple connections, but is mostly single-threaded and can "
            "thus typically only utilize a single CPU core. One process per "
            "available CPU core on the system should maximize performance."
        ),
    )

    parser.set_defaults(need_session=True, run_as_root=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    check()

    overwrite = False

    if os.path.exists(arguments.service_file):
        if arguments.force:
            logger.debug(
                "%s: file already exists; will overwrite", arguments.service_file
            )
            overwrite = True
        else:
            fail("%s: file already exists!" % arguments.service_file)

    service_name = os.path.basename(arguments.service_file)
    dependencies = ["postgresql.service", "critic-main-system.service"]

    parameters = {
        "requires": " ".join(dependencies),
        "after": " ".join(dependencies),
        "criticctl_path": sys.argv[0],
        "processes": arguments.processes,
        "host": arguments.host,
        "port": arguments.port,
        "sockets_dir": sockets_dir(),
        "httpd_username": arguments.httpd_user,
        "httpd_groupname": arguments.httpd_group,
    }

    if arguments.unix:
        parameters["listen_arguments"] = UNIX_ARGUMENTS % parameters
    else:
        parameters["listen_arguments"] = TCP_ARGUMENTS % parameters

    with open(arguments.service_file, "w", encoding="utf-8") as file:
        print((TEMPLATE % parameters).strip(), file=file)

    logger.info("Created systemd service file: %s", arguments.service_file)

    daemon_reload()

    container = await api.systemsetting.fetch(critic, key="frontend.container")

    async with api.transaction.start(critic) as transaction:
        await transaction.modifySystemSetting(container).setValue("aiohttp")
        await transaction.addSystemEvent(
            "install",
            "container",
            "Installed aiohttp service: %s" % arguments.service_file,
            {
                "flavor": "aiohttp",
                "service_file": arguments.service_file,
                "service_name": service_name,
                "processes": arguments.processes,
                "host": arguments.host,
                "port": arguments.port,
                "unix": arguments.unix,
            },
        )

    if arguments.start_service:
        if overwrite:
            restart_service(service_name)
        else:
            start_service(service_name)

    logger.info("Updated Critic's system settings:")
    logger.info("  frontend.container=%s", json.dumps(container.value))

    return 0
