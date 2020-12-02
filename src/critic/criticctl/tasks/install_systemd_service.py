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
import logging
import os
import sys

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from .systemctl import check, start_service, restart_service, daemon_reload
from .utils import fail

TEMPLATE = """

[Unit]
Description=Critic code review system
Requires=postgresql.service
After=postgresql.service

[Service]
Type=forking
PIDFile=%(pidfile_path)s
ExecStart=%(criticctl_path)s run-services
KillMode=mixed
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target

"""

name = "install:systemd-service"
description = "Install a systemd service for the Critic system."


def setup(parser: argparse.ArgumentParser) -> None:
    identity = parser.get_default("configuration")["system.identity"]

    parser.add_argument(
        "--service-file",
        default=f"/etc/systemd/system/critic-{identity}-system.service",
        help="Service file to create.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing service file instead of aborting.",
    )
    parser.add_argument(
        "--start-service",
        action="store_true",
        help="Start the service after creating the service file.",
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

    parameters = {
        "pidfile_path": background.utils.service_pidfile("servicemanager"),
        "criticctl_path": sys.argv[0],
    }

    with open(arguments.service_file, "w", encoding="utf-8") as file:
        print((TEMPLATE % parameters).strip(), file=file)

    logger.info("Created systemd service file: %s", arguments.service_file)

    daemon_reload()

    async with api.transaction.start(critic) as transaction:
        await transaction.addSystemEvent(
            "install",
            "services",
            "Installed systemd service: %s" % arguments.service_file,
            {
                "flavor": "systemd",
                "service_file": arguments.service_file,
                "service_name": service_name,
            },
        )

    if arguments.start_service:
        if overwrite:
            restart_service(service_name)
        else:
            start_service(service_name)

    return 0
