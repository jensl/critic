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
import json
import sys
from typing import Any

from critic import api

name = "settings"
title = "Access Critic's system settings."


class InvalidJSON(Exception):
    pass


def check_json(key: str, value: str) -> Any:
    try:
        return json.loads(value)
    except ValueError as error:
        raise InvalidJSON("%s: invalid value: %s" % (key, error))


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--indent", type=int, help="Amount of indentation in JSON output."
    )
    parser.set_defaults(need_session=True, parser=parser)

    operations = parser.add_subparsers(help="Operation")

    list_parser = operations.add_parser("list", help="List settings.")
    list_parser.set_defaults(operation="list")

    get_parser = operations.add_parser("get", help="Retrieve one or more settings.")
    get_parser.set_defaults(operation="get")
    get_parser.add_argument("key", nargs="+", help="Settings to retrieve.")

    get_all_parser = operations.add_parser("get-all", help="Retrieve all settings.")
    get_all_parser.set_defaults(operation="get-all")
    get_all_parser.add_argument("prefix", nargs="*", help="Filter the settings tree.")

    set_parser = operations.add_parser("set", help="Update a setting's value.")
    set_parser.set_defaults(operation="set")
    set_parser.add_argument(
        "update",
        nargs="+",
        metavar="KEY[:VALUE]",
        help=(
            "Setting update. If the VALUE part is omitted, a single line is "
            "is read from STDIN, and interpreted as the VALUE part. Either "
            "way, the value must be JSON formatted."
        ),
    )

    create_parser = operations.add_parser(
        "create",
        help=(
            "Create a new setting. If --key/--description are "
            "omitted, a JSON structure is read from STDIN instead. "
            "This structure should be a list of objects, where "
            "each object has the keys `key`, `description` and "
            "`value`."
        ),
    )
    create_parser.set_defaults(operation="create")
    create_parser.add_argument("--key", help="The new setting's key.")
    create_parser.add_argument("--description", help="The new setting's description.")
    create_parser.add_argument(
        "--value",
        help=(
            "The new setting's value. If omitted, a single line is read from "
            "STDIN, and interpreted as the value."
        ),
    )


async def main(critic: api.critic.Critic, arguments: Any) -> int:
    if not hasattr(arguments, "operation"):
        arguments.parser.print_help()
        return 0

    response: Any = None

    try:
        if arguments.operation == "list":
            response = [
                setting.id for setting in await api.systemsetting.fetchAll(critic)
            ]
        elif arguments.operation == "get":
            response = {}
            for key in arguments.key:
                setting = await api.systemsetting.fetch(critic, key)
                response[key] = setting.value
        elif arguments.operation == "get-all":

            def include(setting: api.systemsetting.SystemSetting):
                if not arguments.prefix:
                    return True
                for prefix in arguments.prefix:
                    if setting.key.startswith(prefix + "."):
                        return True
                return False

            response = {
                setting.id: setting.value
                for setting in await api.systemsetting.fetchAll(critic)
                if include(setting)
            }
        elif arguments.operation == "set":
            updates = []
            update: str
            for update in arguments.update:
                key, colon, value = update.partition(":")
                setting = await api.systemsetting.fetch(critic, key=key)
                if not colon:
                    value = sys.stdin.readline()
                value = check_json(key, value)
                updates.append((setting, value))
            async with api.transaction.start(
                critic, accept_no_pubsub=True
            ) as transaction:
                for setting, value in updates:
                    await transaction.modifySystemSetting(setting).setValue(value)
            response = None
        elif arguments.operation == "create":
            if arguments.key is not None:
                if arguments.description is None:
                    print("Missing argument: --description", file=sys.stderr)
                    return 1
                if arguments.value:
                    value = arguments.value
                else:
                    value = sys.stdin.readline()
                value = check_json(arguments.key, value)
                async with api.transaction.start(
                    critic, accept_no_pubsub=True
                ) as transaction:
                    await transaction.createSystemSetting(
                        arguments.key, arguments.description, value
                    )
            else:
                settings_input = check_json("<stdin>", sys.stdin.read())
                async with api.transaction.start(
                    critic, accept_no_pubsub=True
                ) as transaction:
                    for setting_input in settings_input:
                        await transaction.createSystemSetting(**setting_input)
            response = None
        else:
            assert not "reached"
    except (api.systemsetting.Error, InvalidJSON) as error:
        print(str(error), file=sys.stderr)
        return 1

    if response is not None:
        json.dump(response, sys.stdout, indent=arguments.indent)
        print()

    return 0
