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
import os
import pathlib
from typing import Protocol

logger = logging.getLogger(__name__)

from critic import api
from critic import base

name = "psql"
title = "Start `psql` against Critic's database"


def setup(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(need_session=False)


class Arguments(Protocol):
    configuration: base.Configuration


async def main(critic: api.critic.Critic, arguments: Arguments) -> int:
    configuration = arguments.configuration
    pgpass = pathlib.Path(configuration["paths.home"]) / ".pgpass"

    kwargs = configuration["database.parameters"]["kwargs"]
    host = str(kwargs["host"])
    port = str(kwargs["port"])
    user = str(kwargs["user"])
    dbname = str(kwargs["dbname"])

    if not pgpass.exists():
        password = kwargs["password"]
        with pgpass.open("w") as pgpass_file:
            pgpass_file.write(f"{host}:{port}:{dbname}:{user}:{password}\n")
        pgpass.chmod(0o600)

    try:
        os.execvpe(
            "psql",
            ["psql", "-h", host, "-p", port, "-U", user, dbname],
            os.environ | {"PGPASSFILE": str(pgpass)},
        )
    except OSError:
        return 1
