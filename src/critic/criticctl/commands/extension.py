# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2021 the Critic contributors, Opera Software ASA
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
from pprint import pformat
import sys
from textwrap import indent
from typing import Any, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic.protocol.extensionhost import (
    CallError,
    CallRequest,
    CallResponse,
    EndpointResponseBodyFragment,
    EndpointResponseEnd,
    EndpointResponsePrologue,
    EndpointRole,
    ResponseItem,
    Role,
    SubscriptionResponseItem,
    SubscriptionRole,
)
from critic import pubsub

name = "extension"
title = "Extension sub-commands"


class Fail(Exception):
    pass


def describe_role(role: Role) -> str:
    if isinstance(role, EndpointRole):
        request = role.request
        return f"endpoint::{role.name}: {request.method} {request.path}"
    if isinstance(role, SubscriptionRole):
        message = role.message
        return f"subscription: {message.channel}"
    return "(unknown)"


async def list_calls(critic: api.critic.Critic, arguments: Any) -> None:
    extension: Optional[api.extension.Extension] = None

    if arguments.extension:
        try:
            extension = await api.extension.fetch(critic, key=arguments.extension)
        except api.extension.InvalidKey:
            raise Fail(f"{arguments.extension}: no such extension")

    calls = await api.extensioncall.fetchAll(
        critic, extension=extension, successful=arguments.successful
    )

    for call in calls:
        if call.successful is True:
            status = "success"
        elif call.successful is False:
            status = "failed"
        else:
            status = "pending"

        call_id = call.id.to_bytes(8, "big", signed=True).hex()

        print(
            " | ".join(
                [
                    f"{call_id:>016s}",
                    f"{status:8s}",
                    call.request_time.isoformat(),
                    describe_role(call.request.role),
                ]
            )
        )


async def fetch_call(
    critic: api.critic.Critic, arguments: Any
) -> api.extensioncall.ExtensionCall:
    try:
        return await api.extensioncall.fetch(
            critic, int.from_bytes(bytes.fromhex(arguments.call_id), "big", signed=True)
        )
    except api.extensioncall.InvalidId:
        raise Fail(f"{arguments.call_id}: no such extension call")


def print_error(error: CallError) -> None:
    print(f"CallError: {error.message}")
    if error.details:
        print(f"    Details: {error.details}")
    if error.traceback:
        print(f"    Traceback:")
        print(indent(error.traceback, "      "))


def print_response(response: CallResponse) -> None:
    print("Response:")
    for item in response.items:
        print("  Item: ", end="")

        if isinstance(item, CallError):
            print_error(item)
        elif item.error:
            print_error(item.error)
        elif isinstance(item, EndpointResponsePrologue):
            print(f"EndpointResponsePrologue: {item.status_code} {item.status_text}")
            if item.headers:
                print("    Headers:")
                for key, value in item.headers:
                    print(f"      {key}: {value}")
        elif isinstance(item, EndpointResponseBodyFragment):
            print(f"EndpointResponseBodyFragment: {len(item.data)} bytes")
        elif isinstance(item, EndpointResponseEnd):
            print(f"EndpointResponseEnd: failed={item.failed}")
        elif isinstance(item, SubscriptionResponseItem):
            print("SubscriptionResponseItem")

    if response.log:
        print("  Log:")
        for record in response.log:
            level = logging.getLevelName(record.level)
            print(f"    {level}: {record.name}: {record.message}")


async def inspect_call(critic: api.critic.Critic, arguments: Any) -> None:
    call = await fetch_call(critic, arguments)

    print(f"Request:\n  {pformat(call.request)}\n")

    if call.response:
        print_response(call.response)


async def repeat_call(critic: api.critic.Critic, arguments: Any) -> None:
    old_call = await fetch_call(critic, arguments)
    old_version = await old_call.version

    async with api.transaction.start(critic) as transaction:
        version_modifier = await transaction.modifyExtensionVersion(old_version)
        call_modifier = await version_modifier.modifyExtensionCall(old_call)
        new_call = (await call_modifier.repeat()).subject

    new_version = await new_call.version
    if old_version != new_version:
        logger.info("Extension has been updated:")
        logger.info(" - old version: %s", old_version.sha1)
        logger.info(" - new version: %s", new_version.sha1)

    print()
    print_response(new_call.response)


def setup(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(need_session=False)

    sub_commands = parser.add_subparsers(help="Sub-commands")

    list_calls_parser = sub_commands.add_parser(
        "list-calls", description="List extension calls."
    )
    list_calls_parser.add_argument(
        "--extension", "-e", help="Filter by extension name."
    )
    status = list_calls_parser.add_mutually_exclusive_group()
    status.add_argument(
        "--successful",
        help="Include only successful calls.",
        action="store_const",
        const=True,
        dest="successful",
    )
    status.add_argument(
        "--failed",
        help="Include only failed calls.",
        action="store_const",
        const=False,
        dest="successful",
    )
    list_calls_parser.set_defaults(handler=list_calls, successful=None)

    inspect_call_parser = sub_commands.add_parser(
        "inspect-call", description="Inspect call details."
    )
    inspect_call_parser.add_argument("call_id")
    inspect_call_parser.set_defaults(handler=inspect_call)

    repeat_call_parser = sub_commands.add_parser(
        "repeat-call", description="Repeat call."
    )
    repeat_call_parser.add_argument("call_id")
    repeat_call_parser.set_defaults(handler=repeat_call)

    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: Any) -> int:
    try:
        await arguments.handler(critic, arguments)
        return 0
    except Fail as fail:
        print(fail, file=sys.stderr)
        return 1
