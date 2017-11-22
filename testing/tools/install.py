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
import subprocess

import testing


def main():
    parser = argparse.ArgumentParser(
        description="Critic testing framework: Quick install utility"
    )

    parser.add_argument(
        "--debug", help="Enable DEBUG level logging", action="store_true"
    )
    parser.add_argument(
        "--quiet", help="Disable INFO level logging", action="store_true"
    )

    parser.add_argument(
        "--commit",
        default="HEAD",
        help="Commit (symbolic ref or SHA-1) to test [default=HEAD]",
    )
    parser.add_argument(
        "--upgrade-from",
        help="Commit (symbolic ref or SHA-1) to install first and upgrade from",
    )

    parser.add_argument(
        "--vm-identifier", required=True, help="VirtualBox instance name or UUID"
    )
    parser.add_argument(
        "--vm-hostname", help="VirtualBox instance hostname [default=VM_IDENTIFIER]"
    )
    parser.add_argument(
        "--vm-snapshot",
        default="clean",
        help="VirtualBox snapshot (name or UUID) to upgrade [default=clean]",
    )
    parser.add_argument(
        "--vm-ssh-port",
        type=int,
        default=22,
        help="VirtualBox instance SSH port [default=22]",
    )
    parser.add_argument(
        "--git-daemon-port", type=int, help="Port to tell 'git daemon' to bind to"
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Install interactively (without arguments)",
    )

    arguments = parser.parse_args()

    logger = testing.configureLogging(arguments)
    logger.info("Critic testing framework: Quick install")

    tested_commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", arguments.commit], encoding="utf-8"
    ).strip()

    if arguments.upgrade_from:
        install_commit = subprocess.check_output(
            ["git", "rev-parse", "--verify", arguments.upgrade_from], encoding="utf-8"
        ).strip()
        upgrade_commit = tested_commit
    else:
        install_commit = tested_commit
        upgrade_commit = None

    install_commit_description = subprocess.check_output(
        ["git", "log", "--oneline", "-1", install_commit], encoding="utf-8"
    ).strip()

    if upgrade_commit:
        upgrade_commit_description = subprocess.check_output(
            ["git", "log", "--oneline", "-1", upgrade_commit], encoding="utf-8"
        ).strip()
    else:
        upgrade_commit_description = None

    instance = testing.virtualbox.Instance(
        arguments,
        install_commit=(install_commit, install_commit_description),
        upgrade_commit=(upgrade_commit, upgrade_commit_description),
    )

    repository = testing.repository.Repository(
        arguments.git_daemon_port, install_commit, arguments.vm_hostname
    )

    mailbox = testing.mailbox.Mailbox()

    with repository, mailbox, instance:
        if not repository.export():
            return

        instance.mailbox = mailbox
        instance.start()

        if arguments.interactive:
            print(
                """
Note: To use the simple SMTP server built into the Critic testing framework,
      enter "host" as the SMTP host and "%d" as the SMTP port.

Also note: The administrator user's password will be "testing" (password
           input doesn't work over this channel.)"""
                % mailbox.port
            )

        instance.install(repository, quick=True, interactive=arguments.interactive)
        instance.upgrade(interactive=arguments.interactive)

        testing.pause("Press ENTER to stop VM: ")

        try:
            while True:
                mail = mailbox.pop()
                logger.info("Mail to <%s>:\n%s" % (mail.recipient, mail))
        except testing.mailbox.MissingMail:
            pass


if __name__ == "__main__":
    main()
