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
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

from critic import api

name = "passwd"
title = "Set user's password"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--username", required=True, help="Name of user whose password to set."
    )

    password_group = parser.add_mutually_exclusive_group(required=True)
    password_group.add_argument("--password", help="New password.")
    password_group.add_argument(
        "--no-password", action="store_true", help="Reset to no password."
    )
    password_group.add_argument(
        "--generate",
        action="store_true",
        help="Generate and set new password, and print to STDOUT.",
    )

    parser.set_defaults(need_session=True)


class Arguments(Protocol):
    username: str
    password: str
    no_password: bool
    generate: bool


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    generated_password: Optional[str] = None

    hashed_password: Optional[str]
    if not arguments.no_password:
        from critic import auth

        if arguments.password:
            password = arguments.password
        else:
            import passlib.pwd

            generated_password = password = passlib.pwd.genword()
        hashed_password = await auth.hashPassword(critic, password)
    else:
        hashed_password = None

    async with api.transaction.start(critic) as transaction:
        modifier = transaction.modifyUser(user)
        if hashed_password:
            await modifier.setPassword(hashed_password=hashed_password)
        else:
            await modifier.resetPassword()

    if arguments.no_password:
        logger.info("%s: password cleared", arguments.username)
    else:
        logger.info("%s: password set", arguments.username)

    if generated_password:
        logger.info("Generated password: %s", generated_password)

    return 0
