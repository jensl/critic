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

name = "addrole"
title = "Assign role(s) to user"


def setup(parser):
    parser.add_argument(
        "--username", required=True, help="Name of user to assign new roles to"
    )
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        choices=("administrator", "repositories", "developer", "newswriter"),
        help=(
            "Role. One of: administrator, repositories, developer, " "and newswriter."
        ),
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    unassigned_roles = []
    for role in arguments.role:
        if user.hasRole(role):
            logger.info("%s: user already has role '%s'", user.name, role)
        else:
            unassigned_roles.append(role)

    async with api.transaction.start(critic) as transaction:
        modifier = transaction.modifyUser(user)

        for role in unassigned_roles:
            modifier.addRole(role)

    for role in unassigned_roles:
        logger.info("Assigned role '%s' to user %s [id=%d]", role, user.name, user.id)
