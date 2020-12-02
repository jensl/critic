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
import concurrent.futures
import contextlib
import datetime
import functools
import logging
import logging.handlers
import os
import pickle
import signal
import struct
import sys
import threading
from queue import Queue
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    BinaryIO,
    ClassVar,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from critic import base
from critic import dbaccess
from critic import pubsub


# class AdministratorMailHandler(logging.Handler):
#     def __init__(self, logfile_path: str):
#         super(AdministratorMailHandler, self).__init__()
#         self.logfile_name = os.path.basename(logfile_path)
#         self.is_sending_mail = False

#     def emit(self, record: Any) -> None:
#         from critic import mailutils

#         if self.is_sending_mail:
#             return
#         self.is_sending_mail = True
#         try:
#             assert self.formatter
#             message = self.formatter.format(record)
#             mailutils.sendAdministratorErrorReport(
#                 None, self.logfile_name, message.splitlines()[0], message
#             )
#         finally:
#             self.is_sending_mail = False


class LogToStream(logging.handlers.QueueHandler):
    def __init__(self, stream: BinaryIO):
        queue: Queue[logging.LogRecord] = Queue()
        super().__init__(queue)
        threading.Thread(target=self.write, args=(stream, queue), daemon=True).start()

    def write(self, stream: BinaryIO, queue: Queue[logging.LogRecord]) -> None:
        while record := queue.get():
            data = pickle.dumps({"log": record})
            try:
                stream.write(struct.pack("!I", len(data)) + data)
                stream.flush()
            except ConnectionError:
                break


class SetContextFilter(logging.Filter):
    def filter(self, record: Any) -> bool:
        if not hasattr(record, "context"):
            record.context = record.name
        if not hasattr(record, "stacktrace"):
            record.stacktrace = ""
        return True


class MaintenanceCallback(Protocol):
    async def __call__(self) -> None:
        ...


class MaintenanceWork:
    minimum_gap = 12 * 60 * 60  # 12 hours

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: MaintenanceCallback,
        hours: int,
        minutes: int,
    ):
        self.loop = loop
        self.callback = callback
        self.hours = hours
        self.minutes = minutes
        self.timestamp = self.loop.time()

    @property
    def should_run(self) -> bool:
        if self.timestamp:
            if self.loop.time() - self.timestamp < self.minimum_gap:
                return False
        now = datetime.datetime.now()
        if now.hour < self.hours:
            return False
        if now.hour == self.hours and now.minute < self.minutes:
            return False
        return True

    async def run(self) -> "asyncio.Future[None]":
        def on_done(task: "asyncio.Future[None]") -> None:
            try:
                task.result()
            except Exception:
                logger.exception("Maintenance work failed")
            self.timestamp = self.loop.time()

        task = asyncio.ensure_future(self.callback())
        task.add_done_callback(on_done)
        return task


T = TypeVar("T")


class BackgroundServiceCallbacks:
    """Callbacks that BackgroundService sub-classes can override.

    The function type of overriding methods (`def` vs `async def`) must match
    the declarations in this interface.
    """

    def will_start(self) -> bool:
        """Called before the service starts.

        If a false value is returned, the service exits immediately with a
        zero exit status, meaning it will be disabled.

        Logging is set up and |self.settings| contains all system settings, but
        nothing else will have been done.
        """
        return True

    async def did_start(self) -> None:
        """Called after all startup operations have been performed.

        This is an appropriate time to e.g. register maintenance work.
        """
        pass

    async def wake_up(self) -> Optional[float]:
        """Called when a SIGHUP has been received."""
        pass

    async def pubsub_connected(self, client: pubsub.Client, /) -> None:
        """Called when a (new) connection has been established to the pub/sub service."""
        pass

    async def pubsub_disconnected(self) -> None:
        """Called when the connection to the pub/sub service is lost."""
        pass

    async def will_stop(self) -> None:
        """Called when SIGTERM has been received, before the event loop stops.

        This function can perform asynchronous operations, but should of course
        not delay too long."""
        pass

    def did_stop(self) -> None:
        """Called when the event loop has stopped."""
        pass


class BackgroundService(BackgroundServiceCallbacks):
    name: ClassVar[str]

    settings: Any
    service_settings: Any

    send_administrator_mails = True
    manage_pidfile = True
    default_max_workers = 1
    log_mode: Optional[Literal["stderr", "binary"]] = None
    log_level: Optional[
        Literal["debug", "info", "warn", "error", "critical", "fatal"]
    ] = None
    want_pubsub = False

    inet_server: Optional[asyncio.AbstractServer]
    unix_server: Optional[asyncio.AbstractServer]

    running_workers: Set["asyncio.Future[Any]"]
    pending_workers: Set["asyncio.Future[Any]"]
    maintenance_tasks: List[MaintenanceWork]

    __wake_up_task: Optional["asyncio.Future[Optional[float]]"]
    __wake_up_call: Optional[asyncio.TimerHandle]

    __pubsub_client: Optional[pubsub.Client]

    def __init__(self) -> None:
        super(BackgroundService, self).__init__()

        self.loop = asyncio.get_event_loop()
        self.unix_server = None
        self.inet_server = None
        self.running_workers = set()
        self.pending_workers = set()
        self.maintenance_tasks = []
        self.is_terminating = False
        self.is_stopping = False
        self.__stopped = asyncio.Event()

        self.__wake_up_task = None  # Current asyncio.Task calling wake_up()
        self.__wake_up_call = None  # Handle for delayed call to wake_up()
        self.__wake_up_again = False

        self.__pubsub_client = None
        self.__pubsub_connected = asyncio.Event()

    @classmethod
    def pidfile_path(cls) -> str:
        return background.utils.service_pidfile(cls.name)

    @classmethod
    def logfile_path(cls) -> str:
        return os.path.join(base.configuration()["paths.logs"], cls.name + ".log")

    @classmethod
    def socket_path(cls) -> Optional[str]:
        return background.utils.service_address(cls.name)

    @classmethod
    def socket_address(cls) -> Optional[Tuple[str, int]]:
        return None

    @classmethod
    def loglevel(cls) -> int:
        loglevel_name = cls.log_level
        if loglevel_name is None:
            loglevel_name = getattr(cls.service_settings, "loglevel", None)
        if loglevel_name is not None:
            return getattr(logging, loglevel_name.upper())
        return logging.INFO

    @classmethod
    def configure_logging(cls) -> None:
        for arg in sys.argv[1:]:
            if arg.startswith("--log-mode="):
                log_mode_arg = arg[len("--log-mode=") :]
                assert log_mode_arg in ("stderr", "binary")
                cls.log_mode = log_mode_arg  # type: ignore
            if arg.startswith("--log-level="):
                log_level_arg = arg[len("--log-level=") :]
                assert log_level_arg in (
                    "debug",
                    "info",
                    "warn",
                    "error",
                    "critical",
                    "fatal",
                )
                cls.log_level = arg[len("--log-level=") :]  # type: ignore

        if cls.log_mode == "stderr":
            formatter = logging.Formatter(
                f"%(levelname)7s  [{cls.name}][%(context)s] %(message)s"
                "%(stacktrace)s"
            )
            handler = logging.StreamHandler()
        else:
            formatter = logging.Formatter(
                "(%(asctime)s)  %(levelname)7s  [%(context)s] %(message)s"
                "%(stacktrace)s"
            )
            handler = logging.handlers.RotatingFileHandler(
                cls.logfile_path(), maxBytes=1024 ** 3, backupCount=5
            )

        handler.setFormatter(formatter)
        handler.setLevel(cls.loglevel())
        handler.addFilter(SetContextFilter())

        root_logger = logging.getLogger()
        root_logger.setLevel(cls.loglevel())
        root_logger.addHandler(handler)

        # if cls.send_administrator_mails:
        #     mail_handler = AdministratorMailHandler(cls.logfile_path())
        #     mail_handler.setFormatter(formatter)
        #     mail_handler.setLevel(logging.WARNING)
        #     root_logger.addHandler(mail_handler)

        if cls.log_mode == "binary":
            root_logger.addHandler(LogToStream(sys.stdout.buffer))

        logging.getLogger("asyncio").setLevel(logging.ERROR)

    @contextlib.asynccontextmanager
    async def start_session(self) -> AsyncIterator[api.critic.Critic]:
        async with api.critic.startSession(for_system=True) as critic:
            self.settings = api.critic.settings()
            self.service_settings = getattr(self.settings.services, self.name, None)
            yield critic

    def run_worker(self, coro_or_future: Awaitable[T]) -> "asyncio.Future[T]":
        async def run() -> T:
            task = asyncio.current_task()
            assert task
            self.pending_workers.add(task)
            async with self.worker_semaphore:
                self.pending_workers.remove(task)
                self.running_workers.add(task)
                try:
                    return await coro_or_future
                finally:
                    self.running_workers.remove(task)

        return self.check_future(run())

    def is_idle(self) -> bool:
        if self.running_workers:
            logger.debug("not idle: %d running workers", len(self.running_workers))
            return False
        if self.pending_workers:
            logger.debug("not idle: %d pending workers", len(self.pending_workers))
            return False
        if self.__wake_up_task:
            return False
        return True

    async def wait_for_idle(self, timeout: Optional[float]) -> None:
        pass

    async def __wait_for_idle(
        self, run_maintenance: bool, *, timeout: Optional[float] = None
    ) -> bool:
        busy_filename = self.pidfile_path() + ".busy"
        assert os.path.isfile(busy_filename)
        if not self.is_idle():
            logger.debug("waiting for idle state")
            deadline = self.loop.time() + timeout if timeout else None
            while not self.is_idle():
                timeout = max(0, deadline - self.loop.time()) if deadline else None
                if self.running_workers:
                    logger.debug(
                        "waiting for %d running workers", len(self.running_workers)
                    )
                    await asyncio.wait(self.running_workers, timeout=timeout)
                elif self.pending_workers:
                    logger.debug(
                        "waiting for %d pending workers", len(self.pending_workers)
                    )
                    await asyncio.wait(self.pending_workers, timeout=timeout)
                elif self.__wake_up_task:
                    logger.debug("waiting for wake_up() task: %r", timeout)
                    await asyncio.wait_for(self.__wake_up_task, timeout)
                else:
                    await self.wait_for_idle(timeout)
                if timeout == 0 and not self.is_idle():
                    logger.warning("timeout waiting for idle state")
                    return False
                await asyncio.sleep(0)
            logger.debug("idle state achieved")
        if run_maintenance and self.maintenance_tasks:
            logger.info("Running maintenance work (forced)")
            await asyncio.wait(
                [maintenance_work.run() for maintenance_work in self.maintenance_tasks]
            )
        logger.info("Reporting idle state")
        os.unlink(busy_filename)
        return True

    async def stop(self) -> None:
        self.is_stopping = True
        await self.will_stop()
        self.__stopped.set()

    def do_wake_up(self) -> None:
        def wake_up_task_done(task: "asyncio.Future[Optional[float]]") -> None:
            assert task is self.__wake_up_task
            self.__wake_up_task = None
            try:
                delay = task.result()
                if delay is not None:
                    logger.debug("scheduling wake up in %.2fs", delay)
                    self.__wake_up_call = self.loop.call_later(delay, self.do_wake_up)
            except Exception:
                logger.exception("wake_up() crashed")
            if self.__wake_up_again:
                self.loop.call_soon(self.do_wake_up)
                self.__wake_up_again = False

        if self.__wake_up_call:
            self.__wake_up_call.cancel()
            self.__wake_up_call = None

        if self.__wake_up_task:
            self.__wake_up_again = True
            return

        self.__wake_up_task = self.check_future(self.wake_up())
        self.__wake_up_task.add_done_callback(wake_up_task_done)

    def interrupt(self) -> None:
        logger.debug("interrupt")
        self.loop.call_soon(self.do_wake_up)

    def terminate(self) -> None:
        logger.debug("terminate")
        self.is_terminating = True
        self.check_future(self.stop())

    def synchronize(self, run_maintenance: bool) -> None:
        logger.info("Synchronizing")
        self.check_future(self.__wait_for_idle(run_maintenance))

    def check_maintenance(self) -> None:
        for maintenance_work in self.maintenance_tasks:
            if maintenance_work.should_run:
                self.check_future(maintenance_work.run())
        self.loop.call_later(300, self.check_maintenance)

    def register_maintenance(
        self, callback: MaintenanceCallback, when: Union[str, Tuple[int, int]]
    ) -> None:
        assert asyncio.iscoroutinefunction(callback)

        if isinstance(when, str):
            hours_str, _, minutes_str = when.partition(":")
            hours = int(hours_str)
            minutes = int(minutes_str)
        else:
            hours, minutes = when

        if not self.maintenance_tasks:
            self.loop.call_soon(self.check_maintenance)

        self.maintenance_tasks.append(
            MaintenanceWork(self.loop, callback, hours, minutes)
        )

    def __startup_finished(self, disabled: bool) -> None:
        starting_filename = self.pidfile_path() + ".starting"
        if os.path.isfile(starting_filename):
            logger.debug("deleting startup sync file: %s", starting_filename)
            os.unlink(starting_filename)
        if not disabled:
            self.do_wake_up()

    async def start(self) -> None:
        logger.info("Starting service")

        self.loop.add_signal_handler(signal.SIGHUP, self.interrupt)
        self.loop.add_signal_handler(signal.SIGTERM, self.terminate)
        self.loop.add_signal_handler(signal.SIGINT, self.terminate)
        self.loop.add_signal_handler(
            signal.SIGUSR1, functools.partial(self.synchronize, run_maintenance=False)
        )
        self.loop.add_signal_handler(
            signal.SIGUSR2, functools.partial(self.synchronize, run_maintenance=True)
        )

        max_workers = getattr(
            self.service_settings, "max_workers", self.default_max_workers
        )
        self.worker_semaphore = asyncio.BoundedSemaphore(max_workers)

        if self.manage_pidfile:
            with open(self.pidfile_path(), "w") as pidfile:
                print(os.getpid(), file=pidfile)

        if getattr(self, "manage_socket", False):
            socket_path = self.socket_path()
            if socket_path:
                logger.info(f"Listening at: unix:{self.socket_path()}")
                self.unix_server = await self.loop.create_unix_server(
                    self.handle_connection, socket_path
                )
            socket_address = self.socket_address()
            if socket_address:
                host, port = socket_address
                if host is None:
                    host = "*"
                logger.info("Listening at: %s:%d", host, port)
                self.inet_server = await self.loop.create_server(
                    self.handle_connection, *socket_address
                )

        if self.want_pubsub:
            self.check_future(self.__pubsub_connect())

        self.check_future(self.did_start()).add_done_callback(
            lambda future: self.__startup_finished(False)
        )

    def handle_connection(self) -> asyncio.StreamReaderProtocol:
        raise Exception("not implemented")

    async def run(self) -> None:
        if not self.will_start():
            logger.info("Service disabled")
            self.__startup_finished(True)
            return

        await self.start()
        await self.__stopped.wait()

        tasks = []

        if self.unix_server:
            self.unix_server.close()
            tasks.append(self.check_future(self.unix_server.wait_closed()))
        if self.inet_server:
            self.inet_server.close()
            tasks.append(self.check_future(self.inet_server.wait_closed()))

        if tasks:
            await asyncio.wait(tasks)

        if self.manage_pidfile:
            try:
                os.unlink(self.pidfile_path())
            except OSError:
                logger.warning("Failed to unlink: %s", self.pidfile_path())

        self.did_stop()

        if self.is_terminating:
            logger.debug("sending SIGTERM to self")

            self.loop.remove_signal_handler(signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGTERM)

    async def __pubsub_connect(self) -> None:
        from .utils import ServiceError

        while not self.is_terminating:
            try:
                async with pubsub.connect(self.name, persistent=True) as client:
                    self.__pubsub_client = client
                    self.__pubsub_connected.set()
                    await self.pubsub_connected(client)
                    try:
                        await client.closed
                    finally:
                        self.__pubsub_connected.clear()
                        self.__pubsub_client = None
                        await self.pubsub_disconnected()
            except ServiceError:
                await asyncio.sleep(1)

    @property
    async def pubsub_client(self) -> pubsub.Client:
        if not self.want_pubsub:
            raise Exception("Pub/Sub connection not requested!")
        if await self.__pubsub_connected.wait():
            assert self.__pubsub_client
            return self.__pubsub_client
        logger.error("pubsub not available")
        raise Exception("Pub/Sub connection not available!")

    def check_future(self, coroutine_or_future: Awaitable[T]) -> "asyncio.Future[T]":
        def check(future: "asyncio.Future[T]") -> None:
            try:
                future.result()
            except Exception:
                logger.exception("Checked coroutine failed: %r", coroutine_or_future)

        future = asyncio.ensure_future(coroutine_or_future, loop=self.loop)
        future.add_done_callback(check)
        return future

    def check_coroutine_threadsafe(
        self, coroutine: Awaitable[T]
    ) -> concurrent.futures.Future[T]:
        def check(future: concurrent.futures.Future[T]) -> None:
            try:
                future.result()
            except Exception:
                logger.exception("Checked coroutine failed!")

        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        future.add_done_callback(check)
        return future


def call(service_class: Type[BackgroundService]) -> None:
    from . import utils

    from critic import bootstrap as _

    utils.running_service_name.set(service_class.name)

    async def run() -> None:
        async with api.critic.startSession(for_system=True):
            settings = api.critic.settings()

        service_class.settings = settings
        service_class.service_settings = getattr(
            settings.services, service_class.name, None
        )

        service_class.configure_logging()

        try:
            service = service_class()
        except Exception:
            logger.exception("Service factory failed")
            return

        logger.debug("starting service")

        try:
            await service.run()
        except Exception:
            logger.exception("Service running failed")
            return

        logger.debug("service stopped")

        await dbaccess.shutdown()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.close()
