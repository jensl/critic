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

import asyncio
import logging
import os
import shlex
import sys
import textwrap

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess

name = "sshd-client"
title = "Internal command invoked for connected SSH clients"
disabled = "SSH_CONNECTION" not in os.environ


def setup(parser):
    parser.set_defaults(must_be_root=False, run_as_anyone=True)


async def main(critic, arguments):
    from critic.auth import accesscontrol

    if "SSH_ORIGINAL_COMMAND" not in os.environ:
        # Interactive login, which we don't allow.
        print(
            textwrap.fill(
                "This system only provides access to Git repositories over SSH, "
                "not interactive logins."
            ),
            file=sys.stderr,
        )
        return 1

    argv = shlex.split(os.environ["SSH_ORIGINAL_COMMAND"])
    command = argv[0]

    if command == "git":
        command = argv[1]
    elif command.startswith("git-"):
        command = command[4:]

    if command == "receive-pack":
        access_type = "write"
    elif command in ("upload-pack", "upload-archive"):
        access_type = "read"
    else:
        print(
            textwrap.fill(
                "This system only provides access to Git repositories over SSH, "
                "not arbitrary command execution."
            ),
            file=sys.stderr,
        )
        return 1

    path = argv[-1].rstrip("/")

    if not path.endswith(".git"):
        path += ".git"

    if path.startswith("/"):
        repository = gitaccess.GitRepository.direct()
        try:
            path = os.path.relpath(path, await repository.repositories_dir())
        finally:
            await repository.close()

    user = await api.user.fetch(critic, name=os.environ["REMOTE_USER"])

    try:
        repository = await api.repository.fetch(critic, path=path)
    except api.repository.InvalidRepositoryPath:
        print(textwrap.fill("Invalid repository path: " + argv[-1]), file=sys.stderr)
        return 1

    await critic.setActualUser(user)

    try:
        await accesscontrol.AccessControl.accessRepository(repository, access_type)
    except accesscontrol.AccessDenied as error:
        print(str(error), file=sys.stderr)
        return 1

    input_queue = asyncio.Queue()
    output_queue = asyncio.Queue()

    class InputProtocol(asyncio.Protocol):
        def data_received(self, data):
            input_queue.put_nowait(data)

        def eof_received(self):
            input_queue.put_nowait(b"")

    await critic.loop.connect_read_pipe(InputProtocol, sys.stdin)
    output_transport, _ = await critic.loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout
    )

    async def handle_output():
        while True:
            data = await output_queue.get()
            if not data:
                output_transport.write_eof()
                break
            output_transport.write(data)

    env = {"REMOTE_USER": critic.actual_user.name}

    await asyncio.gather(
        repository.low_level.stream(command, input_queue, output_queue, env),
        handle_output(),
    )

    return 0
