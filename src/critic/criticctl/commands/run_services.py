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

name = "run-services"
title = "Start Critic background services"
long_description = """

This command starts Critic's background services.

Unless --no-detach is used, the background services run "daemonized", meaning
that this command exits once the services have started.

Note that this command is normally used from a SysV init script or systemd
service definition, and is not intended to be used directly.

"""


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=30,
        help="Amount of time to wait for successful startup confirmation.",
    )
    parser.add_argument(
        "--no-detach",
        action="store_true",
        help=(
            "Do not detach. This also causes all log output to be written to "
            "this command's STDERR instead of to per-service log files."
        ),
    )
    parser.add_argument(
        "--log-mode", choices=("file", "stderr", "binary"), help="Log mode"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Assume existing PID file is stale, and start anyway.",
    )

    parser.set_defaults(run_as_root=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    await critic.close()

    if arguments.no_detach:
        args = ["--no-detach"]
    else:
        args = [f"--startup-timeout={arguments.startup_timeout}"]

    if arguments.force:
        args.append("--force")

    if arguments.log_mode:
        args.append(f"--log-mode={arguments.log_mode}")

    args.append(f"--log-level={logging.getLevelName(arguments.loglevel).lower()}")

    os.execv(
        sys.executable,
        [sys.executable, "-m", "critic.background.servicemanager", "--master", *args],
    )
