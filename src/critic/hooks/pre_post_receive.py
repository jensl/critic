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
import sys
import os
import pwd
import subprocess
import json
import stat


def gitconfig(name):
    process = subprocess.Popen(["git", "config", name], stdout=asyncio.subprocess.PIPE)

    stdout, _ = process.communicate()

    if process.returncode == 0:
        return stdout.decode().strip()


async def communicate(loop, socket_path, repository_name):
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
    except Exception:
        print("Failed to connect to Critic's githook service!")
        return 1

    hook = os.path.basename(sys.argv[0])

    data = {
        "hook": hook,
        "user_name": pwd.getpwuid(os.getuid()).pw_name,
        "repository_name": repository_name,
        "environ": {},
        "refs": [],
    }

    quarantine_path = os.environ.get("GIT_QUARANTINE_PATH")
    if quarantine_path:
        # The quarantine object directory is made inaccessible to group/others
        # by some Git versions (e.g. 2.14.1 on Ubuntu 17.10). This is
        # incompatible with our model of processing the update in a separate
        # process run as another user, so make sure the directory is accessible
        # to the group as well.
        current_mode = stat.S_IMODE(os.stat(quarantine_path).st_mode)
        os.chmod(quarantine_path, current_mode | stat.S_IRWXG)

    for key, value in os.environ.items():
        if key in ("REMOTE_USER", "CRITIC_FLAGS") or key.startswith("GIT_"):
            data["environ"][key] = os.environ[key]

    stdin_reader = asyncio.StreamReader()
    stdin_protocol = asyncio.StreamReaderProtocol(stdin_reader)

    await loop.connect_read_pipe(lambda: stdin_protocol, sys.stdin)

    while True:
        line = await stdin_reader.readline()
        if not line:
            break
        old_sha1, new_sha1, ref_name = line.rstrip().decode().split(" ", 2)
        data["refs"].append(
            {"old_sha1": old_sha1, "new_sha1": new_sha1, "ref_name": ref_name}
        )

    writer.write(json.dumps(data).encode() + b"\n")
    writer.write_eof()

    first = True
    accept = False
    reject = False

    while True:
        line = (await reader.readline()).rstrip()
        if not line:
            break
        data = json.loads(line.decode())
        if "output" in data:
            if first:
                sys.stdout.write("\n")
                first = False
            sys.stdout.write(data["output"])
            sys.stdout.flush()
        if "accept" in data:
            accept = True
        if "reject" in data:
            reject = True

    writer.close()

    if hook == "pre-receive":
        if not (accept or reject):
            # The githook service didn't say whether to accept or reject
            # the update.  We'll reject it.
            print("Invalid response from Critic!")

        return 0 if (accept and not reject) else 1

    return 0


def main():
    socket_path = gitconfig("critic.socket")
    repository_name = gitconfig("critic.name")

    if not socket_path or not repository_name:
        print(
            """Repository is not configured properly!  Please add

[critic]
\tsocket = <socket path>
\tname = <repository name>

to the repository's configuration file."""
        )
        sys.exit(1)

    loop = asyncio.get_event_loop()
    try:
        sys.exit(
            loop.run_until_complete(communicate(loop, socket_path, repository_name))
        )
    finally:
        loop.close()
