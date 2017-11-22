from __future__ import annotations

import asyncio
import contextlib
import grp
import json
import logging
import os
import pwd
import re
import shutil
import signal
import sys
import tempfile
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, TextIO

from . import ControlPipe, Database, activity, execute

logger = logging.getLogger(__name__)

username = pwd.getpwuid(os.geteuid()).pw_name
groupname = grp.getgrgid(os.getegid()).gr_name


class InstallFailed(Exception):
    pass


class System:
    run_frontend: Optional[asyncio.Task]
    run_services: Optional[asyncio.Task]
    server_host: Optional[str]
    server_port: int

    criticctl_path: Optional[str]
    __criticctl_argv: List[str]
    __criticctl_env: Dict[str, str]

    def __init__(self, arguments: Any, state_dir: str, state_is_temporary: bool):
        self.arguments = arguments
        self.database = Database(arguments, state_dir, state_is_temporary)
        self.state_dir = state_dir
        self.state_is_temporary = state_is_temporary

        self.run_frontend = None
        self.run_services = None
        self.server_host = None
        self.server_port = arguments.http_port

        self.criticctl_path = shutil.which("criticctl")
        if self.criticctl_path is None:
            self.criticctl_path = os.path.join(state_dir, "bin", "criticctl")
        else:
            logger.debug("Using `criticctl` from $PATH: %s", self.criticctl_path)

        self.__criticctl_env = {"CRITIC_HOME": state_dir}
        self.controlpipe = ControlPipe(self)

    @staticmethod
    @contextlib.asynccontextmanager
    async def make(arguments: Any) -> AsyncIterator[System]:
        if arguments.state_dir:
            if not os.path.isdir(arguments.state_dir):
                os.makedirs(arguments.state_dir)
            yield System(arguments, arguments.state_dir, False)
        else:
            with tempfile.TemporaryDirectory() as state_dir:
                yield System(arguments, state_dir, True)

    @property
    def server_address(self) -> Optional[str]:
        if self.server_host is None or not self.server_port:
            return None
        return f"{self.server_host}:{self.server_port}"

    async def criticctl(self, *args: str, **kwargs: Any) -> Any:
        assert self.criticctl_path

        output_args = ["--binary-output"]

        if self.arguments.debug:
            output_args.append("--verbose")
        elif self.arguments.quiet:
            output_args.append("--quiet")

        log_filter: Optional[Callable[[str], None]] = kwargs.pop("log_filter", None)
        stdout_sink: Optional[TextIO] = kwargs.pop("stdout_sink", None)

        async def stdout_handler(reader: Optional[asyncio.StreamReader]) -> None:
            assert reader
            client = ControlPipe.Client(reader)
            async for msg in client.read():
                assert isinstance(msg, dict)
                if "log" in msg:
                    record = msg["log"]
                    if log_filter:
                        log_filter(record["message"])
                    logging.getLogger(record["name"]).log(
                        record["level"], record["message"]
                    )
                if "stdout" in msg:
                    if stdout_sink:
                        stdout_sink.write(msg["stdout"])

        kwargs.setdefault("stdout_handler", stdout_handler)

        return await execute(
            self.criticctl_path, *output_args, *args, **kwargs, **self.__criticctl_env
        )

    @property
    def installed(self) -> bool:
        return os.path.isfile(os.path.join(self.state_dir, ".installed"))

    async def install(self) -> None:
        with open(os.path.join(self.state_dir, "quickstart.pid"), "w") as pidfile:
            print(str(os.getpid()), file=pidfile)

        self.criticctl_path = shutil.which("criticctl")

        if self.criticctl_path is None:
            self.criticctl_path = os.path.join(self.state_dir, "bin", "criticctl")

            if not os.path.isfile(os.path.join(self.state_dir, "pyvenv.cfg")):
                with activity("Creating virtual environment"):
                    await execute(sys.executable, "-m", "venv", self.state_dir)

            pip = os.path.join(self.state_dir, "bin", "pip")
            if not os.access(pip, os.F_OK | os.X_OK):
                logger.error("%s: executable not found", pip)
                raise InstallFailed

            if not os.path.isfile(self.criticctl_path):
                with activity("Installing/Upgrading pip+wheel"):
                    await execute(
                        os.path.join(self.state_dir, "bin", "pip"),
                        "install",
                        "--upgrade",
                        "pip",
                        "wheel",
                    )
                with activity("Installing Critic dependencies"):
                    await execute(
                        os.path.join(self.state_dir, "bin", "pip"),
                        "install",
                        "--requirement",
                        "requirements.txt",
                    )
                with activity("Installing Critic package"):
                    await execute(
                        os.path.join(self.state_dir, "bin", "pip"),
                        "install",
                        "-e",
                        os.path.dirname(os.path.abspath(__file__)),
                    )

        if not os.path.isfile(
            os.path.join(self.state_dir, "etc", "configuration.json")
        ):
            with activity("Configuring Critic"):
                install_args = [
                    "--flavor",
                    "quickstart",
                    "--is-testing",
                    "--system-username",
                    username,
                    "--system-groupname",
                    groupname,
                    "--database-name",
                    self.database.name,
                    "--database-username",
                    self.database.username,
                    "--database-password",
                    self.database.password,
                    "--database-host",
                    self.database.host,
                    "--database-port",
                    str(self.database.port),
                    "--database-wait",
                    "30",
                ]

                await self.criticctl("run-task", "install", *install_args)

                updates = [
                    "system.recipients:%s"
                    % json.dumps(self.arguments.system_recipient),
                    "frontend.access_scheme:%s" % json.dumps("http"),
                    "authentication.enable_ssh_access:true",
                    "services.workers.enabled:true",
                    f"services.workers.workers:{self.arguments.worker_processes}",
                    "services.extensionhost.workers:1",
                ]

                if self.arguments.testing:
                    updates.extend(
                        ["authentication.databases.internal.minimum_rounds:1"]
                    )

                if self.arguments.enable_maildelivery:
                    updates.extend(
                        [
                            "smtp.address.host:%s"
                            % json.dumps(self.arguments.smtp_host),
                            "smtp.address.port:%d" % self.arguments.smtp_port,
                        ]
                    )
                    if self.arguments.smtp_username and self.arguments.smtp_password:
                        updates.extend(
                            [
                                "smtp.credentials.username:%s"
                                % json.dumps(self.arguments.smtp_username),
                                "smtp.credentials.password:%s"
                                % json.dumps(self.arguments.smtp_password),
                            ]
                        )
                    updates.append("smtp.configured:true")

                if self.arguments.enable_extensions:
                    updates.extend(
                        [
                            "extensions.enabled:true",
                            "extensions.flavors.native.enabled:true",
                        ]
                    )
                    if self.arguments.system_extensions_dir:
                        updates.append(
                            "extensions.system_dir:%s"
                            % json.dumps(self.arguments.system_extensions_dir)
                        )

                await self.criticctl("settings", "set", *updates)

                if not self.arguments.testing:
                    await self.criticctl(
                        "run-task", "calibrate-pwhash", "--hash-time", "0.01"
                    )

                if not self.arguments.testing:
                    await self.criticctl(
                        "adduser",
                        "--username",
                        self.arguments.admin_username,
                        "--fullname",
                        self.arguments.admin_fullname,
                        "--email",
                        self.arguments.admin_email,
                        "--password",
                        self.arguments.admin_password,
                        "--role",
                        "administrator",
                        "--role",
                        "repositories",
                        "--role",
                        "newswriter",
                        "--role",
                        "developer",
                    )

        with open(os.path.join(self.state_dir, ".installed"), "w") as file:
            print(f"installed at {time.ctime()}", file=file)

    async def start(self) -> bool:
        def run_services() -> Awaitable[bool]:
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

            async def stdout_handler(reader: Optional[asyncio.StreamReader]) -> None:
                assert reader
                client = ControlPipe.Client(reader)
                async for msg in client.read():
                    if isinstance(msg, dict):
                        if "log" in msg:
                            logger.handle(msg["log"])
                            continue
                        if msg.get("event") == "started":
                            future.set_result(True)

            logger.debug("running services")

            self.run_services = asyncio.create_task(
                self.criticctl(
                    "run-services",
                    "--force",
                    "--no-detach",
                    "--log-mode=binary",
                    stdout_handler=stdout_handler,
                )
            )

            return future

        with activity("Starting background services"):
            if not await run_services():
                return False

        has_address = asyncio.Event()

        def extract_address(line: str) -> bool:
            if self.server_address is None:
                if line:
                    match = re.search(r"Listening at http://([^:]+):(\d+)", line)
                    if not match:
                        return True
                    self.server_host = match.group(1)
                    self.server_port = int(match.group(2))
                    self.controlpipe.write(
                        {"http": (self.server_host, self.server_port)}
                    )
                has_address.set()
            return True

        frontend_args = [
            "--flavor",
            self.arguments.http_flavor,
            "--update-identity",
            self.arguments.identity,
        ]
        if self.server_host is not None:
            frontend_args.extend(["--listen-host", self.server_host])
        if self.server_port is not None:
            frontend_args.extend(["--listen-port", str(self.server_port)])
        if self.arguments.http_lb_frontend:
            frontend_args.extend(["--flavor", self.arguments.http_lb_frontend])
        if self.arguments.http_lb_backends:
            frontend_args.extend(["--scale", str(self.arguments.http_lb_backends)])
        if self.arguments.http_profile:
            frontend_args.append("--profile")

        with activity("Starting HTTP front-end (%s)" % self.arguments.http_flavor):
            self.run_frontend = asyncio.create_task(
                self.criticctl(
                    "run-frontend", *frontend_args, log_filter=extract_address
                )
            )

            await asyncio.wait(
                [asyncio.create_task(has_address.wait()), self.run_frontend],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if self.run_frontend.done():
                logger.error("Failed to start HTTP front-end!")
                return False

        self.controlpipe.write({"event": "started"})
        return True

    async def stop(self) -> None:
        if self.run_frontend:
            with activity("Stopping background services"):
                self.run_frontend.cancel()
                try:
                    await self.run_frontend
                except asyncio.CancelledError:
                    pass
            self.server_host = self.run_frontend = None

        if self.run_services:
            with activity("Stopping HTTP front-end"):
                self.run_services.cancel()
                try:
                    await self.run_services
                except asyncio.CancelledError:
                    pass
            self.run_services = None

        # pidfile = os.path.join(self.state_dir, "run", "manager.pid")
        # if os.path.isfile(pidfile):
        #     with open(pidfile, "r", encoding="utf-8") as file:
        #         pid = int(file.read().strip())

        #     with activity("Stopping background services"):
        #         try:
        #             os.kill(pid, signal.SIGTERM)
        #         except OSError:
        #             pass
        #         else:
        #             while os.path.isfile(pidfile):
        #                 await asyncio.sleep(0.1)

        self.controlpipe.write({"event": "stopped"})

    async def restart(self) -> bool:
        await self.stop()
        return await self.start()
