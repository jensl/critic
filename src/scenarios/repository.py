from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
import time
from typing import AsyncIterator, Literal, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

from .arguments import get as get_arguments
from .backend import NotFound
from .session import session


class ExecuteError(Exception):
    pass


async def execute(*argv: str, cwd: Path) -> str:
    logger.info("Running '%s' [in %s]", shlex.join(argv), cwd)
    time_before = time.time()
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise ExecuteError(stderr.decode())
    time_after = time.time()
    if stdout.strip():
        logger.debug("- stdout:\n%s", stdout.decode())
    if stderr.strip():
        logger.debug("- stderr:\n%s", stderr.decode())
    duration = time_after - time_before
    if duration > 1:
        logger.info("Done in %.2f seconds.", duration)
    return stdout.decode()


class LocalRepository:
    def __init__(self, origin: CriticRepository, path: Path):
        self.origin = origin
        self.path = path

    async def run(self, *argv: str) -> str:
        return await execute(*argv, cwd=self.path)


class CriticRepository:
    repository_id: Optional[int]

    def __init__(self, name: str, upstream: str, branches: Sequence[str]):
        self.repository_id = None
        self.name = name
        self.full_name = f"scenarios-{name}"
        self.url = f"{get_arguments().backend}/scenarios/{name}.git"
        self.upstream = upstream
        self.branches = branches

    async def ensure(self) -> None:
        async with session() as backend:
            try:
                response = await backend.get("repositories", name=f"{self.full_name}")
            except NotFound:
                pass
            else:
                self.repository_id = response["id"]
                return

            response = await backend.post(
                "repositories",
                {
                    "name": f"{self.full_name}",
                    "path": f"scenarios/{self.name}.git",
                    "mirror": {
                        "url": self.upstream,
                        "branches": [{"remote_name": name} for name in self.branches],
                    },
                },
            )

    @asynccontextmanager
    async def workcopy(
        self, bare: Optional[bool] = False
    ) -> AsyncIterator[LocalRepository]:
        with TemporaryDirectory() as temporary_dir_str:
            temporary_dir = Path(temporary_dir_str)
            clone_args = ["--bare"] if bare else []
            await execute("git", "clone", *clone_args, self.url, cwd=temporary_dir)
            base_path = temporary_dir / self.name
            workcopy = LocalRepository(
                self, base_path.with_suffix(".git") if bare else base_path
            )
            await workcopy.run("git", "remote", "add", "upstream", self.upstream)
            yield workcopy


RepositoryName = Literal["critic"]

REPOSITORY_INFO: Mapping[RepositoryName, Tuple[str, Sequence[str]]] = {
    "critic": ("https://critic-review.org/critic.git", ("master", "stable/1"))
}


async def ensure(name: RepositoryName) -> CriticRepository:
    upstream, branches = REPOSITORY_INFO[name]
    repository = CriticRepository(name, upstream, branches)
    await repository.ensure()
    return repository
