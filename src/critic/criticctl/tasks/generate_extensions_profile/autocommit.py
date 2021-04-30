import asyncio
import logging
from pathlib import Path
import shutil
from typing import Tuple

logger = logging.getLogger(__name__)

from critic.gitaccess import GitRepository, SHA1, as_sha1


async def git(*args: str, cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "git", *args, stdout=asyncio.subprocess.PIPE, cwd=cwd
    )
    stdout, _ = await process.communicate()
    return stdout.decode()


async def current_sha1(repository: GitRepository) -> Tuple[str, SHA1]:
    name = (await repository.run("describe", "--always", "HEAD")).strip().decode()
    sha1 = as_sha1((await repository.run("rev-parse", "HEAD")).strip().decode())
    return name, sha1


def timestamp(path: Path) -> int:
    mtime = int(path.stat().st_mtime)
    if path.is_dir():
        timestamps = [mtime, *(timestamp(child) for child in path.iterdir())]
        return max(*timestamps) if len(timestamps) > 1 else mtime
    return mtime


async def autocommit(source_dir: Path, repository: GitRepository) -> Tuple[str, SHA1]:
    if not (await repository.run("status", "--short")).strip():
        logger.debug("%s: no local changes detected", source_dir)
        return await current_sha1(repository)

    async with repository.worktree("HEAD", detach=True, checkout=False) as worktree:
        worktree_dir = Path(worktree.get_worktree_path())
        latest_mtime = 0
        for path in source_dir.iterdir():
            if path.name == ".git":
                continue
            latest_mtime = max(latest_mtime, timestamp(path))
            if path.is_dir():
                shutil.copytree(path, worktree_dir / path.name)
            else:
                shutil.copy(path, worktree_dir)
        await repository.run("add", "--all")

        with repository.with_environ(
            GIT_AUTHOR_DATE=f"{latest_mtime} +0000",
            GIT_COMMITTER_DATE=f"{latest_mtime} +0000",
        ):
            await repository.run("commit", "--message=Local uncommitted changes")

        name, sha1 = await current_sha1(repository)

        await repository.run("branch", "-f", "autocommitted", sha1)

        return f"{name}-autocommit", sha1
