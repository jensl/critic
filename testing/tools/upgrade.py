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

import testing

def main():
    parser = argparse.ArgumentParser(
        description="Critic testing framework: instance upgrade utility")
    parser.add_argument("--debug", help="Enable DEBUG level logging", action="store_true")
    parser.add_argument("--quiet", help="Disable INFO level logging", action="store_true")
    parser.add_argument("--vm-identifier", help="VirtualBox instance name or UUID", required=True)
    parser.add_argument("--vm-hostname", help="VirtualBox instance hostname [default=VM_IDENTIFIER]")
    parser.add_argument("--vm-snapshot", help="VirtualBox snapshot (name or UUID) to upgrade", default="clean")
    parser.add_argument("--vm-ssh-port", help="VirtualBox instance SSH port [default=22]", type=int, default=22)
    parser.add_argument("--pause-before-upgrade", help="Pause before upgrading", action="store_true")
    parser.add_argument("--pause-after-upgrade", help="Pause after upgrading", action="store_true")
    parser.add_argument("--install", action="append", help="Install named package")

    arguments = parser.parse_args()

    logger = testing.configureLogging(arguments)
    logger.info("Critic Testing Framework: Instance Upgrade")

    instance = testing.virtualbox.Instance(
        identifier=arguments.vm_identifier,
        snapshot=arguments.vm_snapshot,
        hostname=arguments.vm_hostname,
        ssh_port=arguments.vm_ssh_port)

    with instance:
        instance.start()

        logger.debug("Upgrading guest OS ...")

        update_output = instance.execute(
            ["sudo", "DEBIAN_FRONTEND=noninteractive",
             "apt-get", "-q", "-y", "update"])

        logger.debug("Output from 'apt-get -q -y update':\n" + update_output)

        upgrade_output = instance.execute(
            ["sudo", "DEBIAN_FRONTEND=noninteractive",
             "apt-get", "-q", "-y", "upgrade"])

        logger.debug("Output from 'apt-get -q -y upgrade':\n" + upgrade_output)

        retake_snapshot = False

        if "The following packages will be upgraded:" in upgrade_output.splitlines():
            retake_snapshot = True

        if arguments.install:
            install_output = instance.execute(
                ["sudo", "DEBIAN_FRONTEND=noninteractive",
                 "apt-get", "-q", "-y", "install"] + arguments.install)

            logger.debug("Output from 'apt-get -q -y install':\n" +
                         install_output)

            retake_snapshot = True

        if retake_snapshot:
            logger.info("Upgraded guest OS")
            logger.debug("Retaking snapshot ...")

            instance.retake_snapshot(arguments.vm_snapshot)

            logger.info("Snapshot '%s' upgraded!" % arguments.vm_snapshot)
        else:
            logger.info("No packages upgraded in guest OS")

if __name__ == "__main__":
    main()
