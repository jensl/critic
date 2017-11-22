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
import tempfile
from typing import AsyncIterator

logger = logging.getLogger(__name__)

from critic import base
from critic import gitaccess


@base.asyncutils.contextmanager
async def relay_clone(repository_path: str) -> AsyncIterator[gitaccess.GitRepository]:
    configuration = base.configuration()
    with tempfile.TemporaryDirectory(dir=configuration["paths.scratch"]) as clone_dir:
        process = await asyncio.create_subprocess_exec(
            gitaccess.git(),
            "clone",
            "--bare",
            "--shared",
            repository_path,
            clone_dir,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(
                "Failed to clone repository! Output from `git clone`:\n%s",
                stderr.decode().strip(),
            )
        async with gitaccess.GitRepository.direct(clone_dir) as repository:
            yield repository
