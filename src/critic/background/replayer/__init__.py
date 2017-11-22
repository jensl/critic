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
from typing import Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess


async def list_unmerged_paths(repository: gitaccess.GitRepository) -> Sequence[str]:
    output = await repository.run("status", "--porcelain=2", "-z", "-uno")
    filenames = []

    # Output format:
    # - Header lines, beginning with '#'
    # - Modified paths, beginning with '1' (ordinary) or '2' (copied/renamed)
    # - Unmerged paths, beginning with 'u'
    # - Untracked paths, beginning with '?'
    # - Ignored paths, beginning with '!'

    for line in output.decode().split("\0"):
        # We're only interested in unmerged paths.
        if not line.startswith("u "):
            continue

        # Line format: "u <xy> <sub> <m1> <m2> <m3> <mW> <h1> <h2> <h3> <path>"

        # We only care about the path here. We can't use rpartition()/rsplit(),
        # since the filename can contain spaces.
        filenames.append(line.split(" ", 10)[-1])

    return filenames


def extract_unmerged_paths(replay: api.commit.Commit) -> Sequence[str]:
    lines = replay.message.splitlines()
    if "unmerged paths:" in lines:
        return lines[3:]
    return []
