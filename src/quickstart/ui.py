import aiohttp
import asyncio
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)

from .arguments import Arguments
from .execute import ExecuteError, execute
from .outputmanager import activity
from .system import System


class UI:
    react_ui: Optional["asyncio.Task[Any]"]

    def __init__(self, arguments: Arguments, system: System):
        self.arguments = arguments
        self.system = system
        self.react_ui = None
        self.open_in_browser = arguments.open_in_browser

    @property
    def server_address(self) -> str:
        return f"http://{self.system.server_host}:{self.system.server_port}"

    async def prepare(self) -> None:
        build_py = os.path.join(self.arguments.root_dir, "ui", "build.py")
        start_py = os.path.join(self.arguments.root_dir, "ui", "start.py")

        if self.arguments.build_ui:
            with activity("Building UI"):
                await execute(
                    sys.executable,
                    build_py,
                    "--rebuild",
                    "--install",
                    self.system.state_dir,
                )
        if self.arguments.start_ui:
            env = os.environ.copy()
            env["HOST"] = self.arguments.http_host
            env["PORT"] = str(self.arguments.start_ui)
            self.react_ui = asyncio.create_task(
                execute(
                    sys.executable,
                    start_py,
                    "--backend",
                    self.server_address,
                    env=env,
                )
            )
            # The development front-end will be opened when started.
            self.open_in_browser = False
        if self.arguments.download_ui:
            await self.system.criticctl("run-task", "download-ui")

    async def open(self) -> None:
        if self.arguments.open_in_browser is None:
            async with aiohttp.ClientSession() as session:
                async with session.head(self.server_address) as response:
                    open_in_browser = response.status == 200
        else:
            open_in_browser = self.arguments.open_in_browser

        if open_in_browser:
            logger.debug("Opening UI in default browser.")
            try:
                await execute("xdg-open", self.server_address)
            except ExecuteError:
                logger.warning("Failed to open in browser.")

    async def stop(self) -> None:
        if self.react_ui:
            self.react_ui.cancel()
            try:
                await self.react_ui
            except asyncio.CancelledError:
                pass
