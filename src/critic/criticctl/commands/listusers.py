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
import logging
import sys
from typing import Dict

logger = logging.getLogger(__name__)

from critic import api

name = "listusers"
title = "List users"

FORMATS = {
    "tuples": {
        "pre": "# id, name, email, fullname, status\n[",
        "row": " (%(id)r, %(name)r, %(email)r, %(fullname)r, %(status)r),",
        "post": "]",
    },
    "dicts": {
        "pre": "[",
        "row": (
            " {'id': %(id)r, 'name': %(name)r, 'email': %(email)r, "
            "'fullname': %(fullname)r, 'status': %(status)r},"
        ),
        "post": "]",
    },
    "table": {
        "pre": (
            "  id |    name    |              email             |"
            "            fullname            | status\n"
            "-----+------------+--------------------------------+"
            "--------------------------------+--------"
        ),
        "row": ("%(id)4u | %(name)10s | %(email)30s | %(fullname)-30s |" " %(status)s"),
        "post": "",
    },
}


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        "-f",
        choices=sorted(FORMATS.keys()),
        default="table",
        help="Output format",
    )

    parser.set_defaults(need_session=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
    users = await api.user.fetchAll(critic)

    if arguments.format == "json":
        json.dump(
            [
                {
                    "id": user.id,
                    "name": user.name,
                    "fullname": user.fullname,
                    "email": await user.email,
                    "status": user.status,
                }
                for user in users
            ],
            sys.stdout,
        )
        return 0

    output_format = FORMATS[arguments.format]

    print(output_format["pre"])
    for user in users:
        data: Dict[str, object] = {
            "id": user.id,
            "status": user.status,
            "email": user.email,
        }
        if arguments.format == "table" and user.email is None:
            data["email"] = ""
        if arguments.format != "table" or user.status != "disabled":
            data.update({"name": user.name, "fullname": user.fullname})
        else:
            data.update({"name": "N/A", "fullname": "N/A"})
        print(output_format["row"] % data)
    print(output_format["post"])

    return 0
