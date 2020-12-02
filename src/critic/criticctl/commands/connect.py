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

name = "connect"
title = "Connect external account"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--username", required=True, help="Name of Critic user to connect."
    )
    parser.add_argument(
        "--provider", required=True, help=("External authentication provider.")
    )
    parser.add_argument(
        "--account", required=True, help=("External account identifier.")
    )

    parser.set_defaults(need_session=True)


class Arguments(Protocol):
    username: str
    provider: str
    account: str


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    from critic import auth

    try:
        user = await api.user.fetch(critic, name=arguments.username)
    except api.user.InvalidName:
        logger.error("%s: no such user", arguments.username)
        return 1

    enabled_providers = auth.Provider.enabled()
    provider = enabled_providers.get(arguments.provider)

    if provider is None:
        logger.error("%s: invalid provider", arguments.provider)
        if enabled_providers:
            logger.info(
                "Valid choices are: %s", ", ".join(sorted(enabled_providers.keys()))
            )
        else:
            logger.info("No providers are enabled.")
        return 1

    # If the external account is already registered, make sure it's not already
    # connected to a Critic user.
    external_account: Optional[api.externalaccount.ExternalAccount]
    try:
        external_account = await api.externalaccount.fetch(
            critic, provider_name=arguments.provider, account_id=arguments.account
        )
    except api.externalaccount.NotFound:
        external_account = None
    else:
        if external_account.is_connected:
            other_user = await external_account.user
            assert other_user
            logger.error(
                "%s %r: already connected to Critic user %s",
                provider.getTitle(),
                arguments.account,
                other_user.name,
            )
            return 1

    # Check that the user is not already connected to a different external
    # account from the same provider.
    try:
        connected_account = await api.externalaccount.fetch(
            critic, provider_name=arguments.provider, user=user
        )
    except api.externalaccount.NotFound:
        pass
    else:
        logger.error(
            "%s: user already connected to the %s %r",
            user.name,
            provider.getTitle(),
            connected_account.account_id,
        )
        return 1

    async with api.transaction.start(critic) as transaction:
        if external_account is None:
            external_account = await transaction.createExternalAccount(
                arguments.provider, arguments.account
            )

        await transaction.modifyUser(user).connectTo(external_account)

    logger.info(
        "%s: connected to %s %r", user.name, provider.getTitle(), arguments.account
    )

    return 0
