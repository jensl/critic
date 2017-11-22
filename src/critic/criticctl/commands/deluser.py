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

name = "deluser"
title = "Delete user"
long_description = """

User "deletion" comes in two flavors, neither of which actually fully deletes
the account (due to technical constraints).

The softer mode is "retiring", which simply flags the account as no longer
active (AKA "retired"), and disables email delivery to the user. The user will
still be able to sign in, and if they do, the account is automatically
re-enabled.

The harder mode is "disabling", which flags the account as disabled, and also
resets all identifying user details. All historic actions of the user will be
displayed as having been performed by a "former user". The account remains in
the database with its unique id (and a generated unique user name), still
associated with all historic actions of the user.

"""


def setup(parser):
    parser.add_argument("--username", required=True, help="Name of the user to delete")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--retire",
        action="store_const",
        const="retired",
        dest="status",
        help='Soft delete: flag the user as "retired".',
    )
    mode_group.add_argument(
        "--disable",
        action="store_const",
        const="disabled",
        dest="status",
        help="Hard delete: disable the account permanently.",
    )

    parser.set_defaults(need_session=True)


async def main(critic, arguments):
    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    async with api.transaction.start(critic) as transaction:
        transaction.modifyUser(user).setStatus(arguments.status)

    if arguments.status == "retired":
        logger.info("Retired user %s [id=%d]", arguments.username, user.id)
    else:
        logger.info("Disabled account %s [id=%d]", arguments.username, user.id)
