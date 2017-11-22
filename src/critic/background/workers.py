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
import multiprocessing
import os
import signal
import sys
from typing import Dict, List, Literal, Optional, Tuple

logger = logging.getLogger("critic.background.workers")

from critic import background
from critic.base import binarylog

STDOUT = logging.DEBUG + 1
STDERR = logging.DEBUG + 2


class Workers(background.service.BackgroundService):
    name = "workers"

    __processes: Dict[
        int, Tuple[asyncio.subprocess.Process, asyncio.Future[Literal[True]]]
    ]

    def __init__(self) -> None:
        super().__init__()
        self.__processes = {}
        self.__desired = multiprocessing.cpu_count()

    def will_start(self) -> bool:
        if not self.settings.services.workers.enabled:
            logger.info("Service not enabled")
            return False
        if self.settings.services.workers.workers is not None:
            self.__desired = self.settings.services.workers.workers
        return True

    async def did_start(self) -> None:
        self.check_future(self.__ensure_processes())

    async def will_stop(self) -> None:
        futures = []
        for (process, future) in self.__processes.values():
            logger.debug("stopping worker: pid=%d", process.pid)
            process.send_signal(signal.SIGINT)
            futures.append(future)
        if futures:
            await asyncio.wait(futures)

    async def __run_process(self) -> None:
        process = await asyncio.create_subprocess_exec(
            os.path.join(sys.prefix, "bin", "criticctl"),
            "--binary-output",
            "run-worker",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        future = self.loop.create_future()

        logger.info("Started worker [pid=%d]", process.pid)

        self.__processes[process.pid] = (process, future)

        async def handle_stdout() -> None:
            assert process.stdout
            async for msg in binarylog.read(process.stdout):
                if isinstance(msg, dict) and "log" in msg:
                    binarylog.emit(msg["log"], suffix=str(process.pid))

        async def handle_stderr() -> None:
            assert process.stderr
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                logger.log(STDERR, "[pid=%d] %s", process.pid, line.decode().rstrip())

        tasks: List[asyncio.Future] = [
            self.check_future(handle_stdout()),
            self.check_future(handle_stderr()),
            self.check_future(process.wait()),
        ]

        async def wait() -> None:
            await asyncio.wait(tasks)

            logger.info(
                "Worker stopped [pid=%d, returncode=%d]",
                process.pid,
                process.returncode,
            )

            del self.__processes[process.pid]

            future.set_result(True)

        self.check_future(wait())

    async def __ensure_processes(self) -> None:
        while len(self.__processes) < self.__desired:
            await self.__run_process()


if __name__ == "__main__":
    logging.addLevelName(STDOUT, "STDOUT")
    logging.addLevelName(STDERR, "STDERR")

    background.service.call(Workers)
