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
import importlib
import json
import os
import sys

from critic import api


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension-id", type=int, required=True)
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--authentication-label", action="append", default=[])
    parser.add_argument("role-type", choices=("endpoint", "subscription"))
    parser.add_argument("entrypoint")

    arguments = parser.parse_args()

    module_name, _, function_name = arguments.endpoint.partition(":")

    try:
        module = importlib.import_module(module_name)
    except ImportError as error:


    if not os.path.isfile(arguments.script):
        print("%s: file not found" % arguments.script, file=sys.stderr)
        return 1

    async with api.critic.startSession(for_user=True) as critic:
        if arguments.user_id is None:
            user = api.user.anonymous(critic)
        else:
            user = await api.user.fetch(critic, arguments.user_id)

    await critic.setActualUser(user)
    critic.setAuthenticationLabels(arguments.authentication_label)

    sys.path.insert(0, os.getcwd())

    module = {"critic": critic}

    with open(arguments.script, "r", encoding="utf-8") as file:
        exec(compile(file.read(), arguments.script, "exec"), module)

    if not callable(module.get(arguments.function)):
        print(
            "%s::%s: function not found" % (arguments.script, arguments.function),
            file=sys.stderr,
        )
        return 1

    module[arguments.function](*(json.loads(arg) for arg in arguments.args))


if __name__ == "__main__":
    sys.exit(main() or 0)
