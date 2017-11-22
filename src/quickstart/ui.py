import aiohttp
import asyncio
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class UI:
    react_ui: Optional[asyncio.Task]

    def __init__(self, arguments, system):
        self.arguments = arguments
        self.system = system
        self.react_ui = None

    async def prepare(self) -> None:
        from . import activity, execute

        open_in_browser = self.arguments.open_in_browser

        build_py = os.path.join(self.arguments.root_dir, "ui", "build.py")
        start_py = os.path.join(self.arguments.root_dir, "ui", "start.py")
        react_ui = None

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
                    f"http://{system.server_address}",
                    env=env,
                )
            )
            # The development front-end will be opened when started.
            open_in_browser = False
        if self.arguments.download_ui:
            await self.system.criticctl("run-task", "download-ui")

    async def open(self) -> None:
        from . import ExecuteError, execute

        if self.arguments.open_in_browser is None:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    "http://" + self.system.server_address
                ) as response:
                    open_in_browser = response.status == 200
        else:
            open_in_browser = self.arguments.open_in_browser

        if open_in_browser:
            logger.debug("Opening UI in default browser.")
            try:
                await execute("xdg-open", f"http://{server_address}")
            except ExecuteError:
                logger.warning("Failed to open in browser.")

    async def stop(self) -> None:
        if self.react_ui:
            self.react_ui.cancel()
            try:
                await self.react_ui
            except asyncio.CancelledError:
                pass
