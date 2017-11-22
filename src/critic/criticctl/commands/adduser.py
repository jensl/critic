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

logger = logging.getLogger(__name__)

from critic import api

name = "adduser"
title = "Add user"


def setup(parser):
    parser.add_argument(
        "--username", required=True, help="User name. Must be unique on the system."
    )
    parser.add_argument(
        "--fullname", help="Display name. Defaults to username if not specified."
    )
    parser.add_argument(
        "--email", help="Primary email address, to which Critic sends emails."
    )
    parser.add_argument(
        "--password",
        help=(
            "Initial password. Defaults to a generated one, printed by this " "command."
        ),
    )
    parser.add_argument(
        "--no-password",
        action="store_true",
        help="Skip setting a password. The user will not be able to sign in.",
    )
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        choices=("administrator", "repositories", "developer", "newswriter"),
        help=(
            "System role. One of: administrator, repositories, developer, "
            "and newswriter."
        ),
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    password = None
    password_generated = False

    if not arguments.no_password:
        from critic import auth

        if arguments.password:
            password = arguments.password
        else:
            import passlib.pwd

            password = passlib.pwd.genword()
            password_generated = True
        hashed_password = await auth.hashPassword(critic, password)
    else:
        hashed_password = None

    name = arguments.username.strip()

    fullname = None
    if arguments.fullname:
        fullname = arguments.fullname.strip()
    if not fullname:
        fullname = arguments.username.strip()

    email = None
    if arguments.email:
        email = arguments.email.strip()
    if not email:
        email = None

    try:
        await api.user.fetch(critic, name=name)
    except api.user.InvalidName:
        pass
    else:
        logger.error("%s: user already exists", name)
        return 1

    async with api.transaction.start(critic) as transaction:
        modifier = await transaction.createUser(
            name, fullname, email, hashed_password=hashed_password
        )

        for role in arguments.role:
            modifier.addRole(role)

    user = await modifier

    logger.info("Created user %s [id=%d]", user.name, user.id)

    if password_generated:
        logger.info("Generated password: %s", password)
