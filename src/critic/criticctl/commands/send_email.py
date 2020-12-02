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
import sys
from typing import Dict, Optional

logger = logging.getLogger(__name__)

from critic import api

name = "send-email"
title = "Send email"
long_description = """

Send a custom email using Critic's mail delivery system. The primary use-case
for this command is testing that the mail delivery system is functional.

If no recipients are specified, the email is sent to the configured "system
recipients" that will receive system maintenance messages such as error reports.

"""


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--to", action="append", metavar="ADDRESS", help="Add email recipient."
    )
    parser.add_argument(
        "--subject", default="Critic test email", help="Email subject line."
    )
    parser.add_argument(
        "--header",
        action="append",
        metavar="NAME:VALUE",
        help="Add custom email header.",
    )
    parser.add_argument(
        "--body", help="Email body. If omitted the body is read from STDIN."
    )

    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    if arguments.to:
        recipients = arguments.to
    else:
        recipients = api.critic.settings().system.recipients

    if not recipients:
        logger.error("No recipients specified!")
        return 1

    headers: Optional[Dict[str, str]]
    if arguments.header:
        headers = {}
        for header in arguments.header:
            name, colon, value = header.partition(":")
            if not colon:
                logger.error("Invalid header argument: %r", header)
            headers[name] = value
    else:
        headers = None

    if arguments.body:
        body = arguments.body
    else:
        body = sys.stdin.read()

    # FIXME: Send message using the new protocol!
    # mailutils.sendMessage(recipients, arguments.subject, body, headers=headers)
    #
    # return 0

    logger.debug(f"{body=} {headers=}")

    raise Exception("NOT IMPLEMENTED")
