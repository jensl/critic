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

logger = logging.getLogger(__name__)

from critic import api
from critic.background import extensiontasks

name = "addextension"
title = "Add extension"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--name",
        required=True,
        help="Extension name.",
    )
    parser.add_argument(
        "--url", required=True, help="Git repository URI to clone from."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--install", metavar="VERSION", help="Install VERSION for all users."
    )
    group.add_argument(
        "--install-live",
        action="store_const",
        const=True,
        dest="install",
        help="Install live for all users.",
    )
    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    name = arguments.name.strip()
    url = arguments.url.strip()

    try:
        scan_result = await extensiontasks.scan_external(critic, url)
    except extensiontasks.Error as error:
        logger.error("Failed to scan extension repository: %s", url)
        logger.error("Error: %s", str(error))
        return 1

    if scan_result.versions:
        logger.info("Available versions:")
        for name, _ in sorted(scan_result.versions.items()):
            logger.info(" - %s", name)

    async with api.transaction.start(critic) as transaction:
        extension = (await transaction.createExtension(name, url)).subject

    logger.info("Created extension %s [id=%d]", extension.name, extension.id)

    if arguments.install:
        if arguments.install is True:
            version_name = None
            version_desc = "live version"
        else:
            version_name = arguments.install
            version_desc = f"version {arguments.install}"
        try:
            version = await api.extensionversion.fetch(
                critic,
                extension=extension,
                name=version_name,
            )
        except api.extensionversion.InvalidName:
            logger.error("Extension version not found!")
            return 1

        async with api.transaction.start(critic) as transaction:
            await transaction.installExtension(extension, version)

        logger.info("Installed %s for all users.", version_desc)

    return 0
