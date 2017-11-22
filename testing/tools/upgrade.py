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

import argparse
import time

import testing


def main():
    parser = argparse.ArgumentParser(
        description="Critic testing framework: instance upgrade utility"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable DEBUG level logging"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Disable INFO level logging"
    )

    parser.add_argument_group("VirtualBox instance options")
    parser.add_argument(
        "--identifier",
        required=True,
        dest="vm_identifier",
        metavar="IDENTIFIER",
        help="VirtualBox instance name (or UUID)",
    )
    parser.add_argument(
        "--hostname",
        dest="vm_hostname",
        metavar="HOSTNAME",
        help=("VirtualBox instance hostname " "[default=same as instance name]"),
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        dest="vm_ssh_port",
        metavar="PORT",
        help="VirtualBox instance SSH port [default=22]",
    )
    parser.add_argument(
        "--restore-snapshot",
        required=True,
        dest="vm_snapshot",
        metavar="NAME",
        help="Snapshot to restore before upgrading",
    )
    parser.add_argument(
        "--take-snapshot",
        metavar="NAME",
        help=("Snapshot to take when finished " "[default=same as restored snapshot]"),
    )

    parser.add_argument_group("Mode of operation")
    parser.add_argument(
        "--upgrade", action="store_true", help="Upgrade all installed packages"
    )
    parser.add_argument("--install", action="append", help="Install new package")
    parser.add_argument(
        "--custom",
        action="store_true",
        help=("Pause for custom maintenance " "[default unless --upgrade/--install]"),
    )
    parser.add_argument(
        "--reboot", action="store_true", help="Reboot before retaking snapshot"
    )

    arguments = parser.parse_args()

    logger = testing.configureLogging(arguments)
    logger.info("Critic Testing Framework: Instance Upgrade")

    instance = testing.virtualbox.Instance(arguments)

    if arguments.take_snapshot:
        instance.check_snapshot(arguments.take_snapshot, allow_missing=True)

    with instance:
        instance.start()

        if arguments.upgrade:
            logger.info("Upgrading installed packages ...")
            instance.apt_install(upgrade=True)

        if arguments.install:
            logger.info("Installing new packages ...")
            instance.apt_install(*arguments.install)

        if arguments.custom or not (arguments.upgrade or arguments.install):
            testing.pause()

        if arguments.reboot:
            logger.info("Rebooting ...")
            instance.execute(["sudo", "reboot"])

            logger.debug("Sleeping 10 seconds ...")
            time.sleep(10)

            instance.wait()

            logger.debug("Sleeping 10 seconds ...")
            time.sleep(10)

        logger.debug("Retaking snapshot ...")

        take_snapshot = arguments.take_snapshot or instance.snapshot

        event = instance.retake_snapshot(take_snapshot)

        logger.info("Snapshot %r %s", take_snapshot, event)


if __name__ == "__main__":
    main()
