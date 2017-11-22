# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from .relayclone import relay_clone

from critic import gitaccess
from critic.gitaccess import SHA1


async def perform_update(
    repository_path: str,
    source_url: str,
    remote_name: str,
    local_name: str,
    old_value: Optional[SHA1],
) -> bool:
    logger.info("Checking branch `%s` in %s...", remote_name, source_url)

    async with relay_clone(repository_path) as relay:
        try:
            logger.debug(" - running `git fetch`...")
            await relay.run(
                "fetch", source_url, f"+refs/heads/{remote_name}:FETCH_HEAD",
            )
        except gitaccess.GitError:
            logger.error(" - fetch failed!")
            return False

        new_value = await relay.revparse("FETCH_HEAD")

        if old_value == new_value:
            logger.info(" - already up-to-date")
            return True

        if old_value:
            logger.debug(" - changed: %s -> %s", old_value, new_value)
        else:
            logger.debug(" - created: %s", new_value)

        logger.info(" - pushing to %s", repository_path)

        refname = f"refs/heads/{local_name}"

        try:
            output = await relay.run(
                "push",
                f"--force-with-lease={refname}:{old_value or ''}",
                "origin",
                f"FETCH_HEAD:{refname}",
            )
        except gitaccess.GitError:
            logger.error(" - push failed!")
            return False

        logger.info(" - update finished")

        for line in output.decode().strip().splitlines():
            logger.debug("output: %s", line)

    return True
