from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import pickle
import signal
import struct
import subprocess
from typing import AsyncIterator, Literal, Optional, Tuple, TypedDict

from . import Instance
from .. import Config
from ...utilities import ExecuteResult, execute

logger = logging.getLogger(__name__)


HEADER_FMT = "!I"


class LogMessage(TypedDict):
    name: str
    level: int
    message: str
    traceback: Optional[str]


class ControlPipeMessage(TypedDict):
    log: Optional[LogMessage]

    root_dir: Optional[str]
    criticctl_path: Optional[str]
    http: Optional[Tuple[str, int]]


class ControlPipe:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

    @staticmethod
    async def connect(path: str) -> ControlPipe:
        return ControlPipe(*await asyncio.open_unix_connection(path))

    async def write(self, item: object) -> None:
        data = pickle.dumps(item)
        self.writer.write(struct.pack(HEADER_FMT, len(data)))
        self.writer.write(data)
        await self.writer.drain()

    async def read(self) -> AsyncIterator[ControlPipeMessage]:
        while True:
            try:
                header = await self.reader.readexactly(struct.calcsize(HEADER_FMT))
            except asyncio.IncompleteReadError as error:
                assert not error.partial
                break
            data_len: int = struct.unpack(HEADER_FMT, header)[0]
            yield pickle.loads(await self.reader.readexactly(data_len))


async def read_stdout(reader: Optional[asyncio.StreamReader]) -> None:
    assert reader
    while True:
        line = (await reader.readline()).decode()
        if not line:
            return
        logger.debug("stdout: %s", line.rstrip())


async def read_stderr(reader: Optional[asyncio.StreamReader]) -> None:
    assert reader
    while True:
        line = (await reader.readline()).decode()
        if not line:
            return
        logger.debug("stderr: %s", line.rstrip())


class Quickstart(Instance):
    root_dir: Optional[str]
    criticctl_path: Optional[str]

    def __init__(self, config: Config, workdir: str):
        self.config = config
        self.workdir = workdir
        self.statedir = os.path.join(self.workdir, "state")

        self.root_dir = None
        self.criticctl_path = None
        self.has_details = asyncio.Event()
        self.instance_log_level = getattr(
            logging, self.config.getoption("instance-log-level", "warn").upper()
        )

        logging.getLogger("instance").setLevel(self.instance_log_level)

    @contextlib.asynccontextmanager
    async def run_automatic(self) -> AsyncIterator[None]:
        logger.info("Running quickstart.py ...")

        if self.config.getoption("verbose") > 1:
            loquacity = ["--debug"]
        elif self.config.getoption("verbose") < 0:
            loquacity = ["--quiet"]
        else:
            loquacity = []

        self.quickstart = await asyncio.create_subprocess_exec(
            "python",
            "-u",
            "quickstart.py",
            "--testing=automatic",
            *loquacity,
            f"--state-dir={self.statedir}",
            "--admin-username=admin",
            "--admin-fullname=Testing Administrator",
            "--admin-email=admin@example.org",
            "--admin-password=testing",
            "--http-port=0",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # queue: asyncio.Queue[Tuple[str, Optional[str]]] = asyncio.Queue()

            self.stdout_task = asyncio.create_task(read_stdout(self.quickstart.stdout))
            self.stderr_task = asyncio.create_task(read_stderr(self.quickstart.stderr))

            async with self.__open_controlpipe(wait=True):
                yield

            self.quickstart.send_signal(signal.SIGINT)
        except KeyboardInterrupt:
            logger.debug("interrupt!")
            self.quickstart.send_signal(signal.SIGINT)
        finally:
            await self.quickstart.wait()

    @contextlib.asynccontextmanager
    async def run_manual(self) -> AsyncIterator[None]:
        self.statedir = os.readlink(".state_dir")

        async with self.__open_controlpipe(wait=False):
            yield

    @contextlib.asynccontextmanager
    async def run(self) -> AsyncIterator[None]:
        if os.path.islink(".state_dir"):
            async with self.run_manual():
                yield
        else:
            async with self.run_automatic():
                yield

    async def execute(
        self,
        program: Literal["criticctl"],
        *args: str,
        log_stdout: bool = True,
        log_stderr: bool = True,
    ) -> ExecuteResult:
        assert self.criticctl_path is not None
        if self.config.getoption("verbose") > 0:
            loquacity = ["--verbose"]
        elif self.config.getoption("verbose") < 0:
            loquacity = ["--quiet"]
        else:
            loquacity = []
        env = os.environ.copy()
        env["CRITIC_HOME"] = self.statedir
        return await execute(
            f"criticctl {args[0]}", self.criticctl_path, *loquacity, *args, env=env
        )

    def get_extension_url(self, name: str) -> str:
        return f"file://{self.root_dir}/extensions/{name}/"

    @contextlib.asynccontextmanager
    async def __open_controlpipe(self, *, wait: bool) -> AsyncIterator[None]:
        logger.debug("connecting control pipe...")

        filename = os.path.join(self.statedir, "controlpipe.unix")

        if wait:
            while not os.path.exists(filename):
                await asyncio.sleep(0.1)

        self.controlpipe = await ControlPipe.connect(filename)

        logger.debug("control pipe connected")

        async def run() -> None:
            has_address = False

            async for msg in self.controlpipe.read():
                if (record := msg.get("log")) :
                    logging.getLogger("instance." + record["name"]).log(
                        record["level"], record["message"]
                    )
                    continue
                logger.debug("received msg: %r", msg)
                if (root_dir := msg.get("root_dir")) :
                    self.root_dir = root_dir
                if (criticctl_path := msg.get("criticctl_path")) :
                    self.criticctl_path = criticctl_path
                if (address := msg.get("http")) :
                    self.address = address
                    has_address = True

                if self.root_dir and self.criticctl_path and has_address:
                    self.has_details.set()

        run_task = asyncio.create_task(run())

        logger.debug("waiting for instance details...")
        await self.has_details.wait()

        logger.info(
            "Connected to running instance:\n  root_dir: %s\n  address: %s:%d",
            self.root_dir,
            *self.address,
        )

        try:
            yield
        finally:
            run_task.cancel()
            try:
                await run_task
            except asyncio.CancelledError:
                pass
