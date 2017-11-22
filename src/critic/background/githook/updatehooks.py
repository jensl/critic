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

from __future__ import annotations

import asyncio
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic import gitaccess


async def update_hooks(critic: api.critic.Critic, socket_path: str) -> None:
    configuration = base.configuration()

    repositories_dir = configuration["paths.repositories"]
    executables_dir = configuration["paths.executables"]

    assert isinstance(repositories_dir, str)
    assert isinstance(executables_dir, str)

    def update_hook(path: str, githook_script: str) -> None:
        if os.path.lexists(path):
            if not os.path.islink(path):
                if not os.path.isfile(path):
                    logger.error("%s: expected symlink or regular file", path)
                    return
                logger.warning("%s: expected symlink, found regular file", path)
                logger.warning("%s: renaming to %s.bak", path, os.path.basename(path))
                os.rename(path, path + ".bak")
            elif os.readlink(path) == githook_script:
                logger.debug("%s: already up-to-date", path)
                return
            else:
                logger.info("%s: recreating incorrect link", path)
                os.unlink(path)
        os.symlink(githook_script, path)

    githook_script = os.path.join(executables_dir, "pre-post-receive")
    if not os.access(githook_script, os.X_OK):
        logger.error(
            "%s: executable script not found; won't update repositories", githook_script
        )
        return

    async def git_config(*args: str, cwd: str) -> None:
        process = await asyncio.create_subprocess_exec(
            gitaccess.git(),
            "config",
            *args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(stderr)
            raise Exception("Failed to run Git: git %s" % " ".join(args))

    for repository in await api.repository.fetchAll(critic):
        repository_dir = os.path.join(repositories_dir, repository.path)

        if not os.path.isdir(repository_dir):
            logger.error("%s: repository missing from disk", repository_dir)
            continue

        hooks_dir = os.path.join(repository_dir, "hooks")

        update_hook(os.path.join(hooks_dir, "pre-receive"), githook_script)
        update_hook(os.path.join(hooks_dir, "post-receive"), githook_script)

        await git_config("critic.name", repository.name, cwd=repository_dir)
        await git_config("critic.socket", socket_path, cwd=repository_dir)
