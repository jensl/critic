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
import re

logger = logging.getLogger(__name__)

RE_COMMAND = re.compile(
    # Optional WITH clause first:
    r"(?:WITH\s+\w+\s+\(\)\s+AS\s+\(\)(?:\s*,\s*\w+\s+\(\)\s+AS\s+\(\))*\s*)?"
    # Then query start.
    r"(?:(INSERT\s+INTO|UPDATE|DELETE\s+FROM|SELECT\s.+?\sFROM)\s+(\S+)|"
    r"(?:(SELECT)\s.+))",
    # Let . match line breaks, and ignore case.
    re.DOTALL | re.IGNORECASE,
)


def analyze_query(query: str) -> str:
    """Extract the SQL command and affected table (if any) from a query

    Supported commands are SELECT, UPDATE, INSERT and DELETE.  Any other
    kind of query will raise a ValueError."""

    level = 0
    top_level = ""

    for part in re.split("([()])", query):
        if part == ")":
            level -= 1
        if level == 0:
            top_level += part
        if part == "(":
            level += 1

    match = RE_COMMAND.match(top_level.strip())

    if not match:
        raise ValueError("unrecognized query: %s" % query)

    command, table, select = match.groups()
    if command is not None:
        table = table.strip('"')
        return command.split()[0]
    assert select == "SELECT"
    return select
