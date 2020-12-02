from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import signal
import sys
from typing import Any, cast

from .arguments import Arguments, parse_arguments
from .system import System
from .compilation import Compilation
from .execute import ExecuteError, execute
from .logfilesfollower import LogFilesFollower
from .outputmanager import OutputManager, activity
from .ui import UI
from .wheel import build_wheel

logger = logging.getLogger(__name__)


def getNewestModificationTime(arguments: Any) -> float:
    newest: float = 0
    for dirpath, _, filenames in os.walk(
        os.path.join(arguments.root_dir, "src", "critic")
    ):
        for filename in filenames:
            if filename[0] != "." and filename.endswith(".py"):
                path = os.path.join(dirpath, filename)
                newest = max(os.stat(path).st_mtime, newest)
    return newest


async def run(system: System) -> int:
    arguments = system.arguments

    with activity("Starting PostgreSQL"):
        await system.database.start()

    if not system.installed:
        with activity("Installing Critic", blanklines=True):
            try:
                await system.install()
            except ExecuteError as error:
                logger.error("Failed to install Critic!")
                logger.info(str(error))
                return 1

        if not arguments.testing:
            logger.info(
                "Created administrator user %r with password %r",
                arguments.admin_username,
                arguments.admin_password,
            )

    if arguments.follow_logs:
        LogFilesFollower(
            os.path.join(system.state_dir, "log"), arguments.follow_logs
        ).start()

    with activity("Starting Critic", blanklines=True):
        started_successfully = await system.start()

    if not started_successfully:
        logger.error("Failed to start the system!")
        return 1

    running_mtime = getNewestModificationTime(arguments)

    if arguments.enable_extensions:
        await build_wheel(system, running_mtime)

    logger.info("Listening at: http://%s/", system.server_address)

    if not arguments.testing:
        configuration_output = io.StringIO()
        await system.criticctl("configuration", stdout_sink=configuration_output)
        logger.debug(repr(configuration_output.getvalue()))
        configuration = json.loads(configuration_output.getvalue())

        if not os.listdir(configuration["paths.repositories"]):
            with activity("Creating critic.git repository", blanklines=True):
                await system.criticctl("addrepository", "--name", "critic")

                await execute(
                    "git",
                    "push",
                    os.path.join(system.state_dir, "git", "critic.git"),
                    "HEAD:refs/heads/master",
                )

    if not arguments.quiet:
        OutputManager.blankline()

    if arguments.testing:
        shutdown_requested = asyncio.Event()

        def handle_sigterm() -> None:
            shutdown_requested.set()

        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, handle_sigterm)

        if arguments.testing == "manual":
            os.symlink(system.state_dir, ".state_dir")

        try:
            if arguments.testing == "manual":
                while not shutdown_requested.is_set():
                    try:
                        await asyncio.wait_for(shutdown_requested.wait(), 1)
                    except asyncio.TimeoutError:
                        current_mtime = getNewestModificationTime(arguments)
                        if current_mtime > running_mtime and Compilation.test():
                            with activity("Restarting the system on request"):
                                await system.restart()
                            running_mtime = current_mtime
                            if arguments.enable_extensions:
                                await build_wheel(system, current_mtime)
            else:
                await shutdown_requested.wait()
        finally:
            if arguments.testing == "manual":
                os.unlink(".state_dir")
    else:
        ui = UI(arguments, system)

        await ui.prepare()
        await ui.open()

        while True:
            current_mtime = getNewestModificationTime(arguments)
            if current_mtime > running_mtime:
                with activity(
                    "Sources changed, restarting the system", blanklines=True
                ):
                    if Compilation.test():
                        if not await system.restart():
                            return 1
                if arguments.enable_extensions:
                    await build_wheel(system, current_mtime)

                running_mtime = current_mtime
            else:
                await asyncio.sleep(1)

    return 0


def setup_logging(arguments: Arguments) -> None:
    if arguments.quiet:
        log_level = logging.WARNING
    elif arguments.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    STDOUT = logging.DEBUG + 1
    STDERR = logging.DEBUG + 2

    setattr(logging, "STDOUT", STDOUT)
    setattr(logging, "STDERR", STDERR)

    logging.addLevelName(STDOUT, "STDOUT")
    logging.addLevelName(STDERR, "STDERR")

    OutputManager(arguments).setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(OutputManager.instance)


async def main(root_dir: str) -> int:
    arguments = cast(Arguments, parse_arguments(root_dir))

    setup_logging(arguments)

    if arguments.testing == "manual":
        if os.path.lexists(".state_dir"):
            if not os.path.islink(".state_dir") or os.path.exists(".state_dir"):
                logger.error("File already exists: %s", os.path.abspath(".state_dir"))
                logger.info(
                    "This might indicate you're already running a quickstarted Critic for"
                )
                logger.info(
                    "testing from this directory. If not, you can safely delete the file"
                )
                logger.info("and run this command again.")
                return 1

            logger.info("Removing stale link: %s", os.path.abspath(".state_dir"))
            os.unlink(".state_dir")

        # try:
        #     os.setsid()
        # except OSError:
        #     pass

    logger.info("Critic: Quickstart", extra={"critic.type": "header"})

    while os.getcwd() in sys.path:
        logger.debug("removing $PWD from `sys.path`")
        sys.path.remove(os.getcwd())

    if not Compilation.test():
        return 1

    async with System.make(arguments) as system:
        try:
            return await run(system)
        except KeyboardInterrupt:
            return 0
        finally:
            try:
                with activity("Shutting down..."):
                    await system.stop()
            except Exception:
                logger.exception("Critic shutdown crashed!")

            with activity("Stopping PostgreSQL..."):
                await system.database.stop()
