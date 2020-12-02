# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import argparse
import asyncio
import glob
import grp
import io
import logging
import os
import pickle
import pwd
import queue
import signal
import stat
import struct
import subprocess
import sys
import textwrap
import threading
import time
from typing import Any, Awaitable, Dict, List, Optional, cast

logger = logging.getLogger("critic.background.servicemanager")

from critic import base
from critic import background
from critic.base import binarylog


def process_uptime(pid: int) -> float:
    btime: int

    with open("/proc/stat", "r", encoding="ascii") as proc_stat:
        for line in proc_stat:
            key, _, value = line.strip().partition(" ")
            if key == "btime":
                btime = int(value)
                break
        else:
            return 0

    with open(f"/proc/{pid}/stat", "r", encoding="ascii") as stat_file:
        items = stat_file.read().split()

    return time.time() - (btime + (int(items[21]) / os.sysconf("SC_CLK_TCK")))


def write_logs(queue: queue.Queue[object]) -> None:
    while item := queue.get():
        data = pickle.dumps(item)

        # print(f"writing {len(data)} {data!r}", file=sys.stderr)

        sys.stdout.buffer.write(struct.pack("!I", len(data)) + data)
        sys.stdout.buffer.flush()


class Service:
    task: Optional["asyncio.Task[object]"]
    process: Optional[asyncio.subprocess.Process]

    def __init__(self, name: str):
        self.name = name
        self.task = None
        self.process = None

    @property
    def starting_filename(self) -> str:
        return background.utils.service_pidfile(self.name) + ".starting"


class ServiceManager(
    background.service.BackgroundService  # , background.service.JSONProtocol
):
    name = "manager"

    # The master process manages our pid file, so tell our base class to
    # leave it alone.
    manage_pidfile = False

    service_futures: Dict[str, List["asyncio.Future[bool]"]]

    def __init__(self) -> None:
        super(ServiceManager, self).__init__()
        self.services = {
            service_name: Service(service_name)
            for service_name in self.settings.services.manager.services
        }
        self.service_futures = {}
        if self.log_mode == "binary":
            self.queue: queue.Queue[object] = queue.Queue()
            self.thread = threading.Thread(
                target=write_logs, args=(self.queue,), daemon=True
            )
            self.thread.start()

    def queue_put(self, item: object) -> None:
        if self.log_mode == "binary":
            self.queue.put(item)

    async def run_service(self, service: Service) -> None:
        def signal_futures(is_running: bool) -> None:
            for future in self.service_futures.pop(service.name, []):
                future.set_result(is_running)

        if service.task is not None:
            signal_futures(True)
            return

        service.task = asyncio.current_task()

        logger.info("%s: Starting service", service.name)

        try:
            started = []
            exited = []

            argv = [
                sys.executable,
                "-m",
                f"critic.background.{service.name}",
                f"--log-mode={self.log_mode}",
                f"--log-level={self.log_level}",
            ]

            while not self.is_stopping:
                process = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=1024 ** 3,
                )

                if self.is_stopping:
                    process.terminate()
                    await process.wait()
                    break

                service.process = process

                signal_futures(True)

                logger.info("%s: Started process: pid=%d", service.name, process.pid)

                started.append(self.loop.time())

                async def read_stdout(process: asyncio.subprocess.Process) -> None:
                    assert process.stdout
                    await process.stdout.read()

                stderr_buffer = io.BytesIO()

                async def read_stderr(process: asyncio.subprocess.Process) -> None:
                    assert process.stderr
                    buffered = b""
                    while True:
                        # Foo!
                        data = await process.stderr.read(64 * 1024)
                        if not data:
                            break
                        buffered += data
                        while True:
                            line, nl, buffered = buffered.partition(b"\n")
                            if not nl:
                                buffered = line
                                break
                            line += nl
                            if self.log_mode == "stderr":
                                sys.stderr.write(line.decode())
                                sys.stderr.flush()
                            else:
                                stderr_buffer.write(line)

                async def read_logs(process: asyncio.subprocess.Process) -> None:
                    async for msg in binarylog.read(process.stdout):
                        assert isinstance(msg, dict)
                        msg["service"] = service.name
                        self.queue_put(cast(object, msg))

                tasks: List[Awaitable[object]] = [process.wait(), read_stderr(process)]

                if self.log_mode == "binary":
                    tasks.append(read_logs(process))
                else:
                    tasks.append(read_stdout(process))

                await asyncio.gather(*tasks)

                def ignore_line(line: bytes) -> bool:
                    if b"UserWarning: semaphore_tracker: " in line:
                        return True
                    if b"len(cache))" in line:
                        return True
                    return False

                stderr = b"".join(
                    line
                    for line in stderr_buffer.getvalue().splitlines(True)
                    if not ignore_line(line)
                )

                if stderr:
                    logger.warning(
                        "Output from %s:\n%s",
                        service.name,
                        textwrap.indent(stderr.decode(), "  "),
                    )

                service.process = None

                exited.append(self.loop.time())

                duration = exited[-1] - started[-1]

                logger.info(
                    "%s: Process exited: returncode=%d duration=%.2fs",
                    service.name,
                    process.returncode,
                    duration,
                )

                assert isinstance(process.returncode, int)

                if process.returncode == 0:
                    break

                if process.returncode > 0:
                    if len(started) >= 3 and started[-3] - exited[1] < 3:
                        logger.info(
                            "%s: Service crashing too frequently; will not "
                            "restart automatically",
                            service.name,
                        )
                        break

                if not self.is_stopping:
                    logger.info("%s: Restarting service", service.name)
        except Exception:
            logger.exception("%s: Exception raised while running service", service.name)
        finally:
            service.task = None
            signal_futures(False)

    async def did_start(self) -> None:
        logger.info("Starting services")

        startup_futures = []

        async def start_service(service: Service) -> None:
            logger.debug("%s: startup...", service.name)
            asyncio.ensure_future(self.run_service(service))

        wait_tasks = []

        async def wait_service(service: Service) -> None:
            while os.path.exists(service.starting_filename):
                await asyncio.sleep(1)
            self.queue_put({"event": "service-started", "service": service.name})

        for service_name in self.settings.services.manager.services:
            service = self.services[service_name]
            logger.debug("creating startup sync file: %s", service.starting_filename)
            with open(service.starting_filename, "w") as starting:
                print(time.ctime(), file=starting)
            service_started = self.loop.create_future()
            startup_futures.append(service_started)
            self.service_futures.setdefault(service.name, []).append(service_started)
            await start_service(service)
            wait_tasks.append(asyncio.create_task(wait_service(service)))

        await asyncio.wait(startup_futures)
        await asyncio.wait(wait_tasks)

        logger.debug("services started")

        self.queue_put({"event": "started"})

    async def handle_client_command(self, command: Any) -> Any:
        logger.debug("client command: %r", command)

        if command.get("query") == "status":

            def process_data(
                *,
                process: Optional[asyncio.subprocess.Process] = None,
                pid: Optional[int] = None,
            ) -> Dict[str, Any]:
                if process is not None:
                    pid = process.pid
                if pid is not None:
                    return {"uptime": process_uptime(pid), "pid": pid}
                return {"uptime": None, "pid": None}

            services = {"manager": {"module": "background.servicemanager"}}

            services["manager"].update(process_data(pid=os.getpid()))

            for service in self.services.values():
                services[service.name] = {"module": f"background.{service.name}"}
                services[service.name].update(process_data(process=service.process))

            return {"services": services}

        if command.get("command") == "restart":
            service_name = command.get("service")

            if service_name == "manager":
                self.terminate()
                return {}

            if service_name not in self.services:
                return {"status": "error", "error": f"{service_name}: no such service"}

            service = self.services[service_name]
            service_started = self.loop.create_future()

            self.service_futures.setdefault(service_name, []).append(service_started)

            if service.task is None:
                asyncio.ensure_future(self.run_service(service))
            elif service.process is not None:
                logger.info("%s: Sending SIGTERM", service_name)
                service.process.terminate()

            is_running = await asyncio.wait_for(service_started, command.get("timeout"))

            return {"is_running": is_running}

        # return await super(ServiceManager, self).handle_client_command(command)
        return None

    async def will_stop(self) -> None:
        tasks = []

        logger.info("Shutting down")

        for _, service in sorted(self.services.items(), reverse=True):
            if service.process is not None:
                logger.info("%s: Terminating service", service.name)
                try:
                    service.process.terminate()
                except ProcessLookupError:
                    logger.debug("%s: process already dead?", service.name)
            if service.task is not None:
                tasks.append(service.task)

        _, pending = await asyncio.wait(tasks, timeout=30)

        logger.debug("pending tasks: %r", pending)


def run_master(arguments: Any) -> None:
    configuration = base.configuration()

    pwentry = pwd.getpwnam(configuration["system.username"])
    grentry = grp.getgrnam(configuration["system.groupname"])

    uid = pwentry.pw_uid
    gid = grentry.gr_gid
    home = pwentry.pw_dir

    pidfile_path = background.utils.service_pidfile("manager")

    if os.path.isfile(pidfile_path):
        if arguments.force:
            os.unlink(pidfile_path)
        else:
            print(
                "%s: file exists; daemon already running?" % pidfile_path,
                file=sys.stderr,
            )
            sys.exit(1)

    # Our RUN_DIR (/var/run/critic/IDENTITY) is typically on a tmpfs that gets
    # nuked on reboot, so recreate it with the right access if it doesn't exist.

    def mkdir(path: str, mode: int) -> None:
        if not os.path.isdir(path):
            if not os.path.isdir(os.path.dirname(path)):
                mkdir(os.path.dirname(path), mode)
            os.mkdir(path, mode)
        else:
            os.chmod(path, mode)
        os.chown(path, uid, gid)

    runtime_dir = configuration["paths.runtime"]

    mkdir(runtime_dir, 0o755 | stat.S_ISUID | stat.S_ISGID)
    mkdir(os.path.join(runtime_dir, "sockets"), 0o755)

    scratch_dir = configuration["paths.scratch"]
    mkdir(scratch_dir, 0o755)

    os.environ["HOME"] = home
    os.chdir(home)

    os.setgid(gid)
    os.setuid(uid)

    starting_pattern = os.path.join(os.path.dirname(pidfile_path), "*.starting")

    # Remove any stale/unexpected *.starting files that would otherwise break
    # our startup synchronization.
    for filename in glob.glob(starting_pattern):
        try:
            os.unlink(filename)
        except OSError as error:
            print(error, file=sys.stderr)

    with open(pidfile_path + ".starting", "w") as starting:
        starting.write("%s\n" % time.ctime())

    def wait_for_startup_sync() -> int:
        deadline = time.time() + arguments.startup_timeout
        while True:
            filenames = glob.glob(starting_pattern)
            if not filenames:
                return 0
            if time.time() > deadline:
                break
            time.sleep(0.1)
        print(file=sys.stderr)
        print(
            (
                "Startup synchronization timeout after %d seconds!"
                % arguments.startup_timeout
            ),
            file=sys.stderr,
        )
        print("Services still starting:", file=sys.stderr)
        for filename in filenames:
            print("  " + os.path.basename(filename), file=sys.stderr)
        return 1

    from . import daemon

    with open(pidfile_path, "w") as pidfile:
        if not arguments.no_detach:
            daemon.detach(parent_exit_hook=wait_for_startup_sync)
        pidfile.write("%s\n" % os.getpid())

    os.umask(0o22)

    was_terminated = False

    def terminated(signum: int, *args: Any) -> None:
        nonlocal was_terminated
        was_terminated = True

    signal.signal(signal.SIGTERM, terminated)

    argv = [sys.executable, "-m", "critic.background.servicemanager", "--slave"]

    if arguments.log_mode:
        argv.append(f"--log-mode={arguments.log_mode}")
    elif arguments.no_detach:
        argv.append("--log-mode=stderr")
    else:
        argv.append("--log-mode=file")

    if arguments.log_level:
        argv.append(f"--log-level={arguments.log_level}")

    process: Optional[subprocess.Popen[str]] = None

    while not was_terminated:
        process = subprocess.Popen(argv, encoding="utf-8")

        while not was_terminated:
            try:
                pid, _ = os.waitpid(process.pid, os.WNOHANG)
                if pid == process.pid:
                    process = None
                    break
                time.sleep(0.1)
            except OSError:
                break

    if process:
        try:
            process.send_signal(signal.SIGTERM)
            process.wait()
        except Exception:
            pass

    try:
        os.unlink(pidfile_path)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--slave", action="store_true")
    mode_group.add_argument("--master", action="store_true")

    master_group = parser.add_argument_group("Master mode options")
    master_group.add_argument("--startup-timeout", type=int, default=30)
    master_group.add_argument("--no-detach", action="store_true")
    master_group.add_argument("--force", action="store_true")

    logging_group = parser.add_argument_group("Logging options")
    logging_group.add_argument(
        "--log-mode",
        choices=("file", "stderr", "binary"),
        help=(
            "Log to file or to stderr. Default is 'stderr' if --no-detach is "
            "used, and 'file' otherwise. This also affects individual "
            "service processes."
        ),
    )
    logging_group.add_argument(
        "--log-level", choices=("debug", "info", "warning", "error", "critical")
    )

    arguments = parser.parse_args()

    if arguments.slave:
        # Note: the --log-mode argument is handled separately in
        # BackgroundService.call().
        background.service.call(ServiceManager)
    else:
        run_master(arguments)


if __name__ == "__main__":
    main()
