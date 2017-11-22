import asyncio
import logging
import os
import subprocess
from typing import Any, Awaitable, Callable, Optional, TextIO, Tuple, Union

logger = logging.getLogger(__name__)

LineFilter = Callable[[str], bool]


class ExecuteError(Exception):
    pass


async def log_process_output(
    process: asyncio.subprocess.Process,
    *,
    stdout_handler: Callable[[Optional[asyncio.StreamReader]], Awaitable[None]] = None,
    stdout_sink: TextIO = None,
    stdout_filter: LineFilter = None,
    stderr_handler: Callable[[Optional[asyncio.StreamReader]], Awaitable[None]] = None,
    stderr_sink: TextIO = None,
    stderr_filter: LineFilter = None,
):
    async def log_output(
        reader: Optional[asyncio.StreamReader],
        log_level: int,
        filter: Optional[LineFilter],
        sink: Optional[TextIO],
    ) -> None:
        if not reader:
            return
        while True:
            line = (await reader.readline()).decode()
            if sink:
                sink.write(line + "\n")
            filter_consumed = filter and not filter(line)
            if not line:
                break
            if not filter_consumed and not sink:
                logger.log(log_level, line, extra={"critic.blanklines": False})

    tasks = []

    if stdout_handler:
        tasks.append(stdout_handler(process.stdout))
    else:
        tasks.append(
            log_output(
                process.stdout, getattr(logging, "STDOUT"), stdout_filter, stdout_sink
            )
        )

    if stderr_handler:
        tasks.append(stderr_handler(process.stderr))
    else:
        tasks.append(
            log_output(
                process.stderr, getattr(logging, "STDERR"), stderr_filter, stderr_sink
            )
        )

    await asyncio.wait(tasks)


async def execute(
    *args: str,
    stdout_handler: Callable[[Optional[asyncio.StreamReader]], Awaitable[None]] = None,
    stdout_sink: TextIO = None,
    stdout_filter: LineFilter = None,
    stderr_handler: Callable[[Optional[asyncio.StreamReader]], Awaitable[None]] = None,
    stderr_sink: TextIO = None,
    stderr_filter: LineFilter = None,
    **kwargs: Any,
) -> Optional[Union[Tuple[TextIO, TextIO], TextIO]]:
    commandline = " ".join(map(str, args))
    logger.debug("execute: %s", commandline)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    popen_kwargs = {}
    for key, value in kwargs.items():
        if key.upper() == key:
            env[key] = str(value)
        else:
            popen_kwargs[key] = value

    process = await asyncio.create_subprocess_exec(
        *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **popen_kwargs
    )

    try:
        await asyncio.gather(
            log_process_output(
                process,
                stdout_handler=stdout_handler,
                stdout_sink=stdout_sink,
                stdout_filter=stdout_filter,
                stderr_handler=stderr_handler,
                stderr_sink=stderr_sink,
                stderr_filter=stderr_filter,
            ),
            process.wait(),
        )
    except asyncio.CancelledError:
        if process.returncode is None:
            process.terminate()
            await process.wait()
        raise

    if process.returncode != 0:
        raise ExecuteError(f"Command '{commandline}' returned {process.returncode}")

    if stdout_sink and stderr_sink:
        return (stdout_sink, stderr_sink)
    elif stdout_sink:
        return stdout_sink
    elif stderr_sink:
        return stderr_sink
    else:
        return None
