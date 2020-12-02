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
import signal
import sys
import time

logger = logging.getLogger(__name__)

from critic import api

name = "synchronize-service"
title = "Synchronize background service(s)"
long_description = """

This command "synchronizes" one or more background services, which means to wait
for the services (one at a time) to reach an "idle" state. This is primarily
useful for testing, and is used by Critic's testing framework to avoid timing
issues.

"""


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Number of seconds to wait for successful synchronization.",
    )
    parser.add_argument(
        "--run-maintenance-tasks",
        action="store_true",
        help="Run maintenance tasks once an idle state has been reached.",
    )
    parser.add_argument(
        "service_name", nargs="+", help="Name of service to synchronize."
    )


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    from critic import background

    available_services = api.critic.settings().services.manager.services

    if arguments.run_maintenance_tasks:
        signum = signal.SIGUSR2
    else:
        signum = signal.SIGUSR1

    for service_name in arguments.service_name:
        if service_name not in available_services:
            logger.error("%s: invalid service name", service_name)
            return 1

        logger.debug("%s: synchronizing service", service_name)

        pidfile_path = background.utils.service_pidfile(service_name)

        def get_pid(has_signalled: bool) -> int:
            if not os.path.isfile(pidfile_path):
                if has_signalled:
                    logger.error("%s: service no longer running", service_name)
                else:
                    logger.error("%s: service not running", service_name)
                sys.exit(1)

            with open(pidfile_path, "r", encoding="utf-8") as pidfile:
                pid = int(pidfile.read().strip())

            try:
                os.kill(pid, 0)
            except OSError:
                if has_signalled:
                    logger.error("%s: process died: %d", service_name, pid)
                else:
                    logger.error("%s: stale pid: %d", service_name, pid)
                sys.exit(1)

            return pid

        original_pid = get_pid(False)

        with open(pidfile_path + ".busy", "w"):
            pass

        try:
            os.kill(original_pid, signum)
        except OSError as error:
            logger.error("%s: failed to signal service: %s", service_name, error)
            return 1

        signalled_at = time.time()
        deadline = signalled_at + arguments.timeout

        while os.path.isfile(pidfile_path + ".busy"):
            if time.time() > deadline:
                logger.error(
                    "%s: timeout while waiting for synchronization", service_name
                )
                return 2

            current_pid = get_pid(True)

            if current_pid != original_pid:
                logger.error("%s: service restarted while synchronizing")
                return 1

            time.sleep(0.1)

        logger.info(
            "%s: service synchronized in %.1fs",
            service_name,
            time.time() - signalled_at,
        )

    return 0
