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
import asyncio
from asyncio.transports import WriteTransport
import logging
import os
import shlex
import sys
import textwrap
from typing import cast

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess

name = "sshd-client"
title = "Internal command invoked for connected SSH clients"
disabled = "SSH_CONNECTION" not in os.environ


def setup(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(must_be_root=False, run_as_anyone=True)


async def main(critic: api.critic.Critic, arguments: argparse.Namespace) -> int:
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
    command_arg = argv[0]

    if command_arg == "git":
        command_arg = argv[1]
    elif command_arg.startswith("git-"):
        command_arg = command_arg[4:]

    command = cast(gitaccess.StreamCommand, command_arg)

    access_type: api.accesscontrolprofile.RepositoryAccessType
    if command == "receive-pack":
        access_type = "modify"
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
        async with gitaccess.GitRepository.direct() as gitrepository:
            path = os.path.relpath(path, await gitrepository.repositories_dir())

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

    input_queue: "asyncio.Queue[bytes]" = asyncio.Queue()
    output_queue: "asyncio.Queue[bytes]" = asyncio.Queue()

    class InputProtocol(asyncio.Protocol):
        def data_received(self, data: bytes) -> None:
            input_queue.put_nowait(data)

        def eof_received(self):
            input_queue.put_nowait(b"")

    await critic.loop.connect_read_pipe(InputProtocol, sys.stdin)
    output_transport, _ = await critic.loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout
    )
    output_write_transport = cast(WriteTransport, output_transport)

    async def handle_output():
        while True:
            data = await output_queue.get()
            if not data:
                output_write_transport.write_eof()
                break
            output_write_transport.write(data)

    env = {"REMOTE_USER": os.environ["REMOTE_USER"]}

    await asyncio.gather(
        repository.low_level.stream(command, input_queue, output_queue, env),
        handle_output(),
    )

    return 0
