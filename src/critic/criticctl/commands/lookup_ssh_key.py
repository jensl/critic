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

import logging
import time

logger = logging.getLogger(__name__)

from critic import api

name = "lookup-ssh-key"
title = "Lookup SSH key in Critic's database"
long_description = """

This command is intended to be used as AuthorizedKeysCommand by an OpenSSH
server authenticating users using SSH keys stored in Critic's database.

"""


def setup(parser):
    parser.add_argument("--expected-user", help="Name of user we wish to authenticate.")
    parser.add_argument(
        "--authenticating-user", help="Name of user trying to authenticate."
    )
    parser.add_argument("--key-type", help="SSH key type.")
    parser.add_argument("--key", help="Base64-encoded SSH key.")

    parser.set_defaults(must_be_root=False)


async def main(critic, arguments):
    log_file = open("/tmp/lookup_ssh_key.log", "a")

    print("1", str(time.time()), file=log_file)

    if arguments.authenticating_user == arguments.expected_user:
        usersshkey = await api.usersshkey.fetch(
            critic, key_type=arguments.key_type, key=arguments.key
        )

        if usersshkey:
            user = await usersshkey.user
            print(f'environment="REMOTE_USER={user.name}" {usersshkey}')
            print(f"found key: {usersshkey.id}", file=log_file)
        else:
            print(
                f"no SSH key found: {arguments.key_type} {arguments.key}", file=log_file
            )
    else:
        print(f"wrong user: {arguments.authenticating_user}", file=log_file)

    print("2", str(time.time()), file=log_file)
