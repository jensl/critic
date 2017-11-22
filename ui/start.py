# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
import distutils.spawn
import json
import os
import signal
import subprocess
import sys
import threading


UI_DIR = os.path.dirname(__file__) or "."


def executable_argument(name):
    path = distutils.spawn.find_executable(name)
    if path is None:
        return {"required": True}
    return {"default": path}


async def check_call(*args, **kwargs):
    process = await asyncio.create_subprocess_exec(*args, **kwargs)
    if await process.wait() != 0:
        raise Exception()


async def main():
    parser = argparse.ArgumentParser(
        "Critic UI builder", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--backend", metavar="URL", help="Address (`host[:port]`) of Critic backend"
    )
    parser.add_argument(
        "--backend-tls",
        action="store_true",
        help="The backend supports secure connections (https/wss)",
    )
    parser.add_argument(
        "--update", action="store_true", help="Run `npm update` before starting"
    )

    executables_group = parser.add_argument_group("Executables")
    executables_group.add_argument(
        "--with-npm",
        metavar="PATH",
        help="`npm` executable",
        dest="npm",
        **executable_argument("npm"),
    )

    arguments = parser.parse_args()

    if not os.path.isdir(os.path.join(UI_DIR, "node_modules")):
        await check_call(arguments.npm, "install", cwd=UI_DIR)
    elif arguments.update:
        await check_call(arguments.npm, "update", cwd=UI_DIR)

    security = "s" if arguments.backend_tls else ""

    env = os.environ.copy()
    if arguments.backend:
        env["CRITIC_API_BACKEND"] = f"http{security}://{arguments.backend}"
        env["CRITIC_WS_BACKEND"] = f"ws{security}://{arguments.backend}"

    process = await asyncio.create_subprocess_exec(
        arguments.npm,
        "start",
        cwd=UI_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    async def filter_output(source, target, name):
        while True:
            raw_line = await source.readline()
            if not raw_line:
                break
            line = raw_line.decode().rstrip()
            print("[react-scripts/%s] %s" % (name, line), file=target)
            target.flush()

    stdout_task = asyncio.ensure_future(
        filter_output(process.stdout, sys.stdout, "stdout")
    )
    stderr_task = asyncio.ensure_future(
        filter_output(process.stderr, sys.stderr, "stderr")
    )

    def terminate(*args):
        process.terminate()

    asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, terminate)
    asyncio.get_event_loop().add_signal_handler(signal.SIGINT, terminate)

    wait_task = asyncio.ensure_future(process.wait())

    await asyncio.wait([stdout_task, stderr_task, wait_task])

    return wait_task.result()


if __name__ == "__main__":
    sys.exit(asyncio.get_event_loop().run_until_complete(main()) or 0)
