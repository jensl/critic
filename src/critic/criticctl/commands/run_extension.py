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

import json
import os
import sys

from critic import api
from critic import background

name = "run-extension"
title = "Run (native) extension"
long_description = """

This commands performs a single (native) extension call.

"""


async def process(critic, value):
    if isinstance(value, dict):
        if "__type__" in value:
            fetch = getattr(api, value["__type__"]).fetch
            args = await process(critic, value.get("__args__", ()))
            kwargs = await process(critic, value.get("__kwargs__", {}))
            return await fetch(critic, *args, **kwargs)
        else:
            return {k: await process(critic, v) for k, v in value.items()}
    elif isinstance(value, list):
        return [await process(critic, item) for item in value]
    else:
        return value


def setup(parser):
    parser.add_argument(
        "--installation-id",
        type=int,
        required=True,
        help="Extension installation to run.",
    )

    user_group = parser.add_argument_group("Authentication details")
    user_group.add_argument("--user-id", type=int, help="User to run extension as.")
    user_group.add_argument(
        "--authentication-label",
        action="append",
        default=[],
        help="User's authentication labels.",
    )

    call_group = parser.add_argument_group("Call details")
    call_group.add_argument(
        "script",
        help=(
            "Path of script (*.py file) to load, relative the extension "
            "version's path."
        ),
    )
    call_group.add_argument(
        "function", help="Name of function (defined in extension script) to call."
    )
    call_group.add_argument("arguments", help="JSON encoded function arguments.")


async def main(critic, arguments):
    background.utils._running_service_name = "criticctl run-extension"

    user = await api.user.fetch(critic, arguments.user_id)

    await critic.setActualUser(user)

    critic.setAuthenticationLabels(arguments.authentication_label)

    installation = await api.extensioninstallation.fetch(
        critic, arguments.installation_id
    )

    os.chdir(await installation.runtime_path)
    sys.path.insert(0, os.getcwd())

    module = {"critic": critic}

    with open(arguments.script, "r", encoding="utf-8") as file:
        exec(compile(file.read(), arguments.script, "exec"), module)

    if not callable(module.get(arguments.function)):
        print(
            ("%s::%s: no such function" % (arguments.script, arguments.function)),
            file=sys.stderr,
        )
        return 1

    args, kwargs = await process(critic, json.loads(arguments.arguments))

    module[arguments.function](*args, **kwargs)
