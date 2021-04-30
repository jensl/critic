from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import io
import logging
import os
from pathlib import Path
import pickle
import secrets
import struct
import time
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
)

from critic.criticctl.utils import is_quickstarted

logger = logging.getLogger(__name__)

from critic import api
from critic.protocol.extensionhost import (
    CallError,
    CallResponseItem,
    EndpointRequest,
    ResponseErrorPackage,
    ResponseFinalPackage,
    ResponseItemPackage,
    ResponsePackage,
    SubscriptionMessage,
    CommandPackage,
)
from critic import base
from critic.base import asyncutils, binarylog

from .prepareextension import prepare_extension
from .state import STATE

HEADER_FMT = "!I"
MAXIMUM_IDLE_TIME = 30

RoleType = Literal["endpoint", "subscription"]
Entrypoint = api.extensionversion.ExtensionVersion.Entrypoint


class Stopped(Exception):
    pass


class Process:
    __response_queue: "asyncio.Queue[Optional[ResponsePackage]]"
    __stop_after: float
    __log_capture: Optional[Callable[[binarylog.BinaryLogRecord], None]]

    def __init__(
        self,
        extension: Extension,
        role_type: RoleType,
        entrypoint: Entrypoint,
        process: asyncio.subprocess.Process,
        unregister: Callable[[], bool],
        *,
        command_writer: asyncio.StreamWriter,
        log_reader: asyncio.StreamReader,
        response_reader: asyncio.StreamReader,
    ):
        self.__extension = extension
        self.__role_type = role_type
        self.__entrypoint = entrypoint
        self.__process = process
        self.__unregister = unregister
        self.__command_writer = command_writer
        self.__log_reader = log_reader
        self.__response_reader = response_reader
        self.__response_queue = asyncio.Queue()
        self.__lock = asyncio.Lock()

        self.__stdout_data = io.BytesIO()
        self.__stderr_data = io.BytesIO()
        self.__log_capture = None

        asyncio.create_task(self.__read_logging(), name="read logging")
        asyncio.create_task(self.__read_responses(), name="read responses")
        asyncio.create_task(
            self.__read_output(process.stdout, self.__stdout_data),
            name="read stdout",
        )
        asyncio.create_task(
            self.__read_output(process.stderr, self.__stderr_data),
            name="read stderr",
        )

        self.__stopped = asyncio.Event()
        self.__schedule_stop()

        asyncio.create_task(self.__stop())

    @property
    def pid(self) -> int:
        return self.__process.pid

    async def __write_command(self, package: CommandPackage) -> None:
        package_data = pickle.dumps(package)
        self.__command_writer.write(
            struct.pack(HEADER_FMT, len(package_data)) + package_data
        )
        await self.__command_writer.drain()

    async def __read_logging(self) -> None:
        async for msg in binarylog.read(self.__log_reader):
            if isinstance(msg, dict) and "log" in msg:
                record = cast(binarylog.BinaryLogRecord, msg["log"])
                binarylog.emit(
                    record,
                    suffix=str(self.__process.pid),
                )
                if self.__log_capture:
                    self.__log_capture(record)

    async def __read_responses(self) -> None:
        header_size = struct.calcsize(HEADER_FMT)
        try:
            while True:
                try:
                    header = await self.__response_reader.readexactly(header_size)
                except asyncio.IncompleteReadError as error:
                    assert not error.partial
                    return
                data_len: int = struct.unpack(HEADER_FMT, header)[0]
                package = pickle.loads(
                    await self.__response_reader.readexactly(data_len)
                )
                if isinstance(package, CallError):
                    logger.error(
                        "%s: %s\n%s",
                        package.message,
                        package.details,
                        package.traceback,
                    )
                assert isinstance(package, ResponsePackage), package
                await self.__response_queue.put(package)
        finally:
            await self.__response_queue.put(None)

    async def __read_output(
        self, stream: Optional[asyncio.StreamReader], sink: io.BytesIO
    ) -> None:
        assert stream
        while True:
            data = await stream.read(65536)
            if not data:
                return
            sink.write(data)

    @asynccontextmanager
    async def lock(self) -> AsyncIterator[Process]:
        logger.debug("locking process: pid=%d", self.__process.pid)
        async with self.__lock:
            if self.__stopped.is_set():
                raise Stopped()
            logger.debug("process locked: pid=%d", self.__process.pid)
            yield self
        logger.debug("process unlocked: pid=%d", self.__process.pid)

    async def handle(
        self,
        user_id: Union[Literal["anonymous", "system"], int],
        accesstoken_id: Optional[int],
        command: Union[EndpointRequest, SubscriptionMessage],
        log_capture: Callable[[binarylog.BinaryLogRecord], None],
    ) -> AsyncIterator[CallResponseItem]:
        token = secrets.token_hex(4)

        logger.debug(
            "%s:%s:%s[pid=%d]: handling command: %r [token=%s]",
            self.__extension.extension_name,
            self.__role_type,
            self.__entrypoint.name,
            self.__process.pid,
            command,
            token,
        )

        assert self.__log_capture is None
        self.__log_capture = log_capture

        try:
            await self.__write_command(
                CommandPackage(token, user_id, accesstoken_id, command)
            )

            while True:
                package = await self.__response_queue.get()

                if not package:
                    stderr_output = self.__stderr_data.getvalue()
                    if stderr_output:
                        logger.warn(
                            "%s:%s:%s[pid=%d]: stderr:\n%s",
                            self.__extension.extension_name,
                            self.__role_type,
                            self.__entrypoint.name,
                            self.__process.pid,
                            stderr_output.decode(),
                        )
                    raise Exception("Unexpected EOF from extension process")

                assert package.token == token

                if isinstance(package, ResponseItemPackage):
                    yield package.response_item
                elif isinstance(package, ResponseErrorPackage):
                    yield package.error
                else:
                    assert isinstance(package, ResponseFinalPackage)
                    break
        finally:
            assert self.__log_capture is log_capture
            self.__log_capture = None
            self.__schedule_stop()

    def __schedule_stop(self) -> None:
        self.__stop_after = time.time() + MAXIMUM_IDLE_TIME

    async def __stop(self):
        while not self.__stopped.is_set():
            async with self.__lock:
                time_remaining = self.__stop_after - time.time()
                if time_remaining <= 0:
                    self.__stopped.set()
                    if not self.__unregister():
                        return
                    break
            await asyncio.wait(
                [asyncio.sleep(time_remaining), self.__stopped.wait()],
                return_when=asyncio.FIRST_COMPLETED,
            )

        logger.debug(
            "%s:%s:%s[pid=%d]: stopping process...",
            self.__extension.extension_name,
            self.__role_type,
            self.__entrypoint.name,
            self.__process.pid,
        )

        self.__command_writer.write_eof()
        try:
            await asyncio.wait_for(self.__process.wait(), timeout=30)
        except asyncio.TimeoutError:
            self.__process.kill()
            await self.__process.wait()

    async def stop(self):
        self.__stopped.set()
        await self.__process.wait()


class EndpointProcess:
    name: str


class SubscriptionProcess:
    entrypoint: str


EXTENSIONS: Dict[int, "asyncio.Future[Extension]"] = {}


class Extension:
    __prepare_task: Awaitable[None]
    __processes: Dict[Tuple[RoleType, str], Process]

    def __init__(
        self,
        extension_name: str,
        version_id: int,
        venv_path: Path,
        manifest: api.extensionversion.ExtensionVersion.Manifest,
    ):
        self.extension_name = extension_name
        self.version_id = version_id
        self.venv_path = venv_path
        self.manifest = manifest

        self.__processes = {}

    @property
    def processes(self) -> Iterable[Process]:
        return self.__processes.values()

    @asynccontextmanager
    async def ensure_process(
        self, role_type: RoleType, entrypoint: Entrypoint
    ) -> AsyncIterator[Process]:
        process_key = (role_type, entrypoint.name)

        async def start() -> None:
            executable = os.path.join(self.venv_path, "bin", "run-native-extension")
            assert os.access(executable, os.F_OK | os.X_OK)

            log_rfd, log_wfd = os.pipe()
            command_rfd, command_wfd = os.pipe()
            response_rfd, response_wfd = os.pipe()

            process = await asyncio.create_subprocess_exec(
                executable,
                f"--log-fd={log_wfd}",
                f"--command-fd={command_rfd}",
                f"--response-fd={response_wfd}",
                f"--role-type={role_type}",
                f"--target={entrypoint.target}",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                pass_fds=(log_wfd, command_rfd, response_wfd),
            )
            os.close(log_wfd)
            os.close(command_rfd)
            os.close(response_wfd)

            logger.info(
                "%s:%s:%s[pid=%d]: started process",
                self.extension_name,
                role_type,
                entrypoint.name,
                process.pid,
            )

            def unregister() -> bool:
                try:
                    del self.__processes[process_key]
                except KeyError:
                    return False
                else:
                    return True

            self.__processes[process_key] = Process(
                self,
                role_type,
                entrypoint,
                process,
                unregister,
                command_writer=await asyncutils.create_writer(command_wfd),
                log_reader=await asyncutils.create_reader(log_rfd),
                response_reader=await asyncutils.create_reader(response_rfd),
            )

            async def monitor(process: asyncio.subprocess.Process) -> None:
                await process.wait()

                logger.info(
                    "%s:%s:%s[pid=%d]: process exited with status %d",
                    self.extension_name,
                    role_type,
                    entrypoint.name,
                    process.pid,
                    process.returncode,
                )

                try:
                    del self.__processes[process_key]
                except KeyError:
                    pass

            asyncio.create_task(monitor(process), name="process monitor")

        while True:
            try:
                process = self.__processes[process_key]
            except KeyError:
                logger.debug("no process found: %r", process_key)
            else:
                try:
                    async with process.lock():
                        yield process
                        return
                except Stopped:
                    logger.debug(
                        "process stopped: %r [pid=%d]", process_key, process.pid
                    )

            await start()

    @staticmethod
    async def ensure(version_id: int) -> Extension:
        async def create() -> Extension:
            async with api.critic.startSession(for_system=True) as critic:
                version = await api.extensionversion.fetch(critic, version_id)
                manifest = await version.manifest

                extension = Extension(
                    (await version.extension).name,
                    version.id,
                    STATE.base_dir / version.sha1,
                    manifest,
                )

                critic_wheel: Optional[Path] = None
                source_dir: Optional[Path] = None

                if is_quickstarted():
                    paths_source = base.configuration()["paths.source"]
                    assert paths_source is not None
                    source_dir = Path(paths_source)
                else:
                    critic_wheel = STATE.critic_wheel

                extension.__prepare_task = asyncio.create_task(
                    prepare_extension(
                        critic_wheel,
                        source_dir,
                        extension.venv_path,
                        extension.extension_name,
                        extension.version_id,
                        extension.manifest,
                    )
                )
                return extension

        async def ensure() -> Extension:
            try:
                future = EXTENSIONS[version_id]
            except KeyError:
                logger.debug("preparing version: %r", version_id)
                future = EXTENSIONS[
                    version_id
                ] = asyncio.get_running_loop().create_future()
                future.set_result(await create())
            else:
                logger.debug("using version: %r", version_id)

            extension = await future
            logger.debug(f"{extension=}")
            await extension.__prepare_task
            logger.debug("prepared!")
            return extension

        return await ensure()

    @staticmethod
    async def shutdown():
        tasks = []
        for extension in EXTENSIONS.values():
            for process in (await extension).processes:
                tasks.append(asyncio.create_task(process.stop()))
        if tasks:
            await asyncio.wait(tasks)