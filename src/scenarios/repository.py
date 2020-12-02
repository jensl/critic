import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

from .arguments import get as get_arguments
from .backend import NotFound
from .session import session


async def execute(*argv: str, cwd: Path) -> str:
    logger.debug("execute: %s [in %s]", shlex.join(argv), cwd)
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(stderr.decode())
    if stdout.strip():
        logger.debug("- stdout:\n%s", stdout.decode())
    if stderr.strip():
        logger.debug("- stderr:\n%s", stderr.decode())
    return stdout.decode()


class LocalRepository:
    def __init__(self, path: Path):
        self.path = path

    async def run(self, *argv: str) -> str:
        return await execute(*argv, cwd=self.path)


class CriticRepository:
    repository_id: Optional[int]

    def __init__(self, name: str, upstream: str):
        self.repository_id = None
        self.name = name
        self.url = f"{get_arguments().backend}/scenarios/{name}.git"
        self.upstream = upstream

    async def ensure(self) -> None:
        async with session() as backend:
            try:
                response = await backend.get(
                    "repositories", name=f"scenarios-{self.name}"
                )
            except NotFound:
                pass
            else:
                self.repository_id = response["id"]
                return

            response = await backend.post(
                "repositories",
                {
                    "name": f"scenarios-{self.name}",
                    "path": f"scenarios/{self.name}.git",
                    "mirror": {"url": self.upstream},
                },
            )

    @asynccontextmanager
    async def workcopy(self) -> AsyncIterator[LocalRepository]:
        with TemporaryDirectory() as temporary_dir_str:
            temporary_dir = Path(temporary_dir_str)
            await execute("git", "clone", self.url, cwd=temporary_dir)
            workcopy = LocalRepository(temporary_dir / self.name)
            await workcopy.run("git", "remote", "add", "upstream", self.upstream)
            yield workcopy


async def ensure(name: str, upstream: str) -> CriticRepository:
    repository = CriticRepository(name, upstream)
    await repository.ensure()
    return repository
