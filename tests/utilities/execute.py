from __future__ import annotations

import asyncio
import dataclasses
import io
import logging
import os
import re
import shlex
import signal
import snapshottest
import subprocess
from typing import Any, Dict, Literal, Optional, Sequence, Set, TextIO, Tuple

logger = logging.getLogger(__name__)


class ExecuteError(Exception):
    def __init__(
        self, returncode: int, stdout: str, stderr: str,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclasses.dataclass
class ExecuteResult:
    returncode: int
    stdout: str
    stderr: str

    def raise_for_status(self) -> ExecuteResult:
        if self.returncode != 0:
            raise ExecuteError(self.returncode, self.stdout, self.stderr)
        return self

    def filter(self, label: str, pattern: str) -> ExecuteResult:
        instances: Dict[str, int] = {}

        def replacement(match):
            index = instances.setdefault(match[0], len(instances))
            return f"<anonymized {label} #{index}>"

        stdout = re.sub(pattern, replacement, self.stdout)
        stderr = re.sub(pattern, replacement, self.stderr)
        if stdout == self.stdout and stderr == self.stderr:
            raise Exception(f"pattern match nothing: {pattern!r}")
        return ExecuteResult(self.returncode, stdout, stderr)

    def to_json(self) -> dict:
        return dict(
            returncode=self.returncode,
            stdout=self.stdout.splitlines(),
            stderr=self.stderr.splitlines(),
        )


class ExecuteResultFormatter(snapshottest.formatters.BaseFormatter):
    def can_format(self, value: object) -> bool:
        return isinstance(value, ExecuteResult)

    def format(self, value: ExecuteResult, indent: Any, formatter: Any) -> Any:
        return snapshottest.formatters.format_dict(
            self.normalize(value, formatter), indent, formatter
        )

    def normalize(self, value: ExecuteResult, formatter: Any) -> Any:
        return value.to_json()


snapshottest.formatter.Formatter.register_formatter(ExecuteResultFormatter())


async def execute(
    description: str,
    *argv: str,
    cwd=None,
    env=None,
    stdin: str = None,
    log_stdout: bool = True,
    log_stderr: bool = True,
) -> ExecuteResult:
    logger.info(
        "execute[%s]: %s (in %s)", description, shlex.join(argv), cwd or os.getcwd()
    )

    if env is None:
        _env = None
    else:
        _env = os.environ.copy()
        _env.update(env)

    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=_env,
    )

    logger.debug("execute[%s]: started, pid=%d", description, process.pid)

    stdout_result = io.StringIO()
    stderr_result = io.StringIO()

    async def write_to_pipe(
        prefix: str, pipe: Optional[asyncio.StreamWriter], data: Optional[str]
    ) -> None:
        assert pipe
        if data:
            pipe.write(data.encode())
            await pipe.drain()
        pipe.close()
        await pipe.wait_closed()
        # logger.debug("%s: closed", prefix)

    async def read_from_pipe(
        prefix: str,
        pipe: Optional[asyncio.StreamReader],
        collect: TextIO,
        log_output: bool,
    ) -> None:
        assert pipe
        while True:
            line = (await pipe.readline()).decode()
            if not line:
                # if log_output:
                #     logger.debug("%s: <eof>", prefix)
                break
            # if log_output:
            #     logger.debug("%s: %s", prefix, line.rstrip())
            collect.write(line)

    tasks = [
        asyncio.create_task(process.wait()),
        asyncio.create_task(
            write_to_pipe(f"execute[{description}]: stdin", process.stdin, stdin)
        ),
        asyncio.create_task(
            read_from_pipe(
                f"execute[{description}]: stdout",
                process.stdout,
                stdout_result,
                log_stdout,
            )
        ),
        asyncio.create_task(
            read_from_pipe(
                f"execute[{description}]: stderr",
                process.stderr,
                stderr_result,
                log_stderr,
            )
        ),
    ]

    await asyncio.wait(tasks)

    if process.returncode != 0:
        logger.info(
            "execute[%s]: exited, returncode=%d", description, process.returncode
        )

    return ExecuteResult(
        process.returncode, stdout_result.getvalue(), stderr_result.getvalue()
    )
