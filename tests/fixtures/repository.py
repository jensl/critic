from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import pytest
import subprocess
import tempfile
from typing import Any, AsyncIterator, Literal, Mapping, Optional, TextIO, Union, cast

from ..utilities import ExecuteResult, Anonymizer, execute, raise_for_status
from .instance import Instance, User
from .api import API
from .websocket import WebSocket
from . import Request, generate_name

logger = logging.getLogger(__name__)


def ensure_dir(path: str) -> str:
    try:
        os.mkdir(path)
    except OSError:
        pass

    assert os.path.isdir(path), path
    return path


@pytest.fixture(scope="session")
def git_askpass(workdir: str) -> str:
    filename = os.path.join(
        ensure_dir(os.path.join(workdir, "scripts")), "git-askpass.sh"
    )
    with open(filename, "w") as file:
        print("#!/bin/sh\necho $GIT_PASSWORD\n", file=file)
    os.chmod(filename, 0o755)
    return filename


class GitBase:
    def __init__(
        self,
        path: str,
        anonymizer: Anonymizer,
        user: Optional[User],
        git_askpass: Optional[str] = None,
    ):
        self.path = path
        self.anonymizer = anonymizer
        self.user = user
        self.git_askpass = git_askpass

    async def execute(
        self,
        git: Literal["git"],
        command: str,
        *args: str,
        env: Mapping[str, str] = {},
        stdin: Optional[str] = None,
    ) -> ExecuteResult:
        use_env = {}
        if self.user:
            use_env.update(
                {
                    "GIT_AUTHOR_NAME": self.user.fullname,
                    "GIT_AUTHOR_EMAIL": self.user.email,
                    "GIT_COMMITTER_NAME": self.user.fullname,
                    "GIT_COMMITTER_EMAIL": self.user.email,
                }
            )
            if self.git_askpass:
                use_env.update(
                    {
                        "GIT_ASKPASS": self.git_askpass,
                        "GIT_PASSWORD": self.user.password,
                    }
                )
        if env:
            use_env.update(env)
        logger.debug("env: %r", use_env)
        return await execute(
            f"{git}-{command}",
            git,
            command,
            *args,
            cwd=self.path,
            env=use_env,
            stdin=stdin,
        )

    async def create_empty_commit(self) -> str:
        assert self.user
        sha1 = raise_for_status(
            await self.execute(
                "git",
                "commit-tree",
                "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
                stdin="Initial empty commit",
            )
        ).stdout.strip()
        self.anonymizer.define(True, CommitSHA1={"initial": sha1})
        return sha1


class Worktree(GitBase):
    async def checkout(
        self,
        ref: str,
        *,
        detach: bool = False,
        create_branch: Optional[str] = None,
        reset_branch: Optional[str] = None,
        track: Optional[Union[str, Literal[True]]] = None,
    ) -> ExecuteResult:
        args = []
        if detach:
            args.append("--detach")
        if create_branch:
            args.extend(["-b", create_branch])
            if track:
                raise_for_status(await self.execute("git", "fetch"))
                if track is True:
                    track = create_branch
                args.extend(["-t", track])
        if reset_branch:
            args.extend(["-B", reset_branch])

        return raise_for_status(await self.execute("git", "checkout", *args, ref))

    @contextlib.asynccontextmanager
    async def edit(
        self, filename: str, mode: Literal["w", "a"] = "w"
    ) -> AsyncIterator[TextIO]:
        with open(os.path.join(self.path, filename), mode) as file:
            yield cast(TextIO, file)
        raise_for_status(await self.execute("git", "add", filename))

    async def delete(self, filename: str) -> None:
        raise_for_status(await self.execute("git", "rm", filename))

    # async def checkout(
    #     self, ref: Optional[str] = None, tracking: bool = False
    # ) -> ExecuteResult:
    #     args = []
    #     if tracking:
    #         raise_for_status(await self.execute("git", "fetch"))
    #         args
    #     return raise_for_status(await self.execute("git", "checkout", ref))

    async def commit(self, message: str, *, amend: bool = False) -> ExecuteResult:
        args = ["-m", message]
        if amend:
            args.append("--amend")
        result = raise_for_status(await self.execute("git", "commit", *args))
        await self.define_sha1(message)
        return result

    async def push_new(self) -> ExecuteResult:
        return raise_for_status(
            await self.execute("git", "push", "-u", "origin", await self.head_name())
        )

    async def push(
        self, *, remote: str = "origin", delete: bool = False, force: bool = False
    ) -> ExecuteResult:
        args = []
        if delete:
            args.append("--delete")
        if force:
            args.append("--force")
        local_name = await self.head_name()
        if await self.config(f"branch.{local_name}.remote") == remote:
            upstream_name = await self.config(f"branch.{local_name}.merge")
            refspec = f"{local_name}:{upstream_name}"
        else:
            refspec = local_name
        return raise_for_status(
            await self.execute("git", "push", *args, remote, refspec)
        )

    async def head_sha1(self) -> str:
        return raise_for_status(
            await self.execute("git", "rev-parse", "HEAD")
        ).stdout.strip()

    async def head_name(self) -> str:
        return raise_for_status(
            await self.execute("git", "symbolic-ref", "--short", "HEAD")
        ).stdout.strip()

    async def define_sha1(self, label: str) -> None:
        self.anonymizer.define(True, CommitSHA1={label: await self.head_sha1()})

    async def config(self, name: str) -> Optional[str]:
        result = await self.execute("git", "config", "--get", name)
        if result.returncode == 0:
            return result.stdout.strip()
        elif result.returncode != 1:
            raise_for_status(result)
        return None


class LocalRepository(GitBase):
    def __init__(
        self,
        workdir: str,
        name: str,
        path: str,
        anonymizer: Anonymizer,
        *,
        user: Optional[User] = None,
        git_askpass: Optional[str] = None,
    ):
        super().__init__(path, anonymizer, user, git_askpass)
        self.workdir = workdir
        self.name = name

    async def configure(self):
        raise_for_status(await self.execute("git", "config", "core.abbrev", "40"))

    @staticmethod
    @contextlib.asynccontextmanager
    async def initialize(
        workdir: str, name: str, user: User, anonymizer: Anonymizer
    ) -> AsyncIterator[LocalRepository]:
        basedir = ensure_dir(os.path.join(workdir, "repositories"))

        with tempfile.TemporaryDirectory(
            prefix=f"{name}-", suffix=".git", dir=basedir
        ) as path:
            raise_for_status(await execute("git-init", "git", "init", "--bare", path))
            repository = LocalRepository(workdir, name, path, anonymizer, user=user)
            await repository.configure()
            raise_for_status(
                await repository.execute(
                    "git", "branch", "master", await repository.create_empty_commit()
                )
            )
            yield repository

    @staticmethod
    @contextlib.asynccontextmanager
    async def clone(
        workdir: str,
        name: str,
        url: str,
        anonymizer: Anonymizer,
        *,
        user: Optional[User],
        git_askpass: Optional[str] = None,
        fetch: bool = True,
    ) -> AsyncIterator[LocalRepository]:
        basedir = ensure_dir(os.path.join(workdir, "repositories"))
        with tempfile.TemporaryDirectory(prefix=f"{name}-", dir=basedir) as path:
            if fetch:
                raise_for_status(await execute("git-clone", "git", "clone", url, path))
            else:
                raise_for_status(await execute("git-init", "git", "init", path))
            repository = LocalRepository(
                workdir, name, path, anonymizer, user=user, git_askpass=git_askpass
            )
            await repository.configure()
            if not fetch:
                raise_for_status(
                    await repository.execute("git", "remote", "add", "origin", url)
                )
            yield repository

    @contextlib.asynccontextmanager
    async def worktree(
        self,
        commit: Optional[str] = None,
        *,
        new_branch: Optional[str] = None,
    ) -> AsyncIterator[Worktree]:
        basedir = ensure_dir(os.path.join(self.workdir, "worktrees"))

        args = []

        if new_branch:
            args.extend(["-b", new_branch])
        elif commit:
            args.append("--detach")

        with tempfile.TemporaryDirectory(prefix=f"{self.name}-", dir=basedir) as path:
            args.append(path)
            if commit:
                args.append(commit)
            raise_for_status(await self.execute("git", "worktree", "add", *args))
            yield Worktree(path, self.anonymizer, self.user, self.git_askpass)

        subprocess.call(["git", "worktree", "prune"])

    @contextlib.asynccontextmanager
    async def daemon(self) -> AsyncIterator[None]:
        logger.debug("starting git daemon in %s", self.path)
        path = self.path

        async def handle_connection(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            git_daemon = await asyncio.create_subprocess_exec(
                "git",
                "daemon",
                "--inetd",
                "--log-destination=stderr",
                "--export-all",
                f"--base-path={os.path.dirname(path)}",
                path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            async def forward(
                reader: Optional[asyncio.StreamReader],
                writer: Optional[asyncio.StreamWriter],
            ) -> None:
                assert reader and writer
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
                writer.write_eof()

            await asyncio.gather(
                asyncio.create_task(forward(reader, git_daemon.stdin)),
                asyncio.create_task(forward(git_daemon.stdout, writer)),
            )

            await git_daemon.wait()

        server = await asyncio.start_server(handle_connection, host="127.0.0.1", port=0)

        assert server.sockets
        host, port = server.sockets[0].getsockname()
        self.url = f"git://{host}:{port}/{os.path.basename(path)}"
        logger.debug("started git daemon @ %s", self.url)

        async with server:
            yield


@pytest.fixture
async def empty_repo(
    request: Request, workdir: str, alice: User, anonymizer: Anonymizer
) -> AsyncIterator[LocalRepository]:
    async with LocalRepository.initialize(
        workdir, request.node.name, alice, anonymizer
    ) as repository:
        async with repository.daemon():
            yield repository


class CriticRepository:
    id: int
    url: str

    def __init__(
        self,
        workdir: str,
        instance: Instance,
        api: API,
        websocket: WebSocket,
        git_askpass: str,
        admin: User,
        anonymizer: Anonymizer,
        name: str,
        *,
        delete_on_exit: bool,
    ):
        self.workdir = workdir
        self.instance = instance
        self.api = api
        self.websocket = websocket
        self.git_askpass = git_askpass
        self.admin = admin
        self.anonymizer = anonymizer
        self.name = name
        self.unique_name = generate_name(name)
        self.delete_on_exit = delete_on_exit

    async def __create(self) -> None:
        async with self.api.session(self.admin) as as_admin:
            logger.debug("creating repository: %s", self.name)

            repository = raise_for_status(
                await as_admin.post(
                    "repositories",
                    {"name": self.unique_name, "path": f"{self.unique_name}.git"},
                )
            ).data["repositories"][0]

            logger.info("Created repository: %s", self.name)

        self.id = repository["id"]
        self.anonymizer.define(RepositoryId={self.name: self.id})
        self.anonymizer.define(RepositoryName={self.name: self.unique_name})
        self.anonymizer.define(RepositoryPath={self.name: f"{self.unique_name}.git"})

        # for url in repository["urls"]:
        #     if url.startswith("http"):
        #         self.url = url
        #         break
        # else:
        #     pytest.fail("No HTTP repository URL returned!")

        self.url = f"{self.api.frontend.prefix}/{repository['path']}"

        async with self.clone(self.admin, fetch=False) as clone:
            sha1 = await clone.create_empty_commit()
            raise_for_status(
                await clone.execute(
                    "git",
                    "push",
                    "origin",
                    f"{sha1}:refs/heads/master",
                )
            )

        master = raise_for_status(
            await self.api.get(
                f"repositories/{self.id}", include="branches", head="branch"
            )
        ).data["linked"]["branches"][0]

        self.anonymizer.define(BranchId={"master": master["id"]})

    async def __delete(self) -> None:
        async with self.api.session(self.admin) as as_admin:
            raise_for_status(await as_admin.delete(f"repositories/{self.id}"))
            await self.websocket.pop(
                action="deleted", resource_name="repositories", object_id=self.id
            )

    @contextlib.asynccontextmanager
    async def clone(
        self, user: Optional[User] = None, fetch: bool = True
    ) -> AsyncIterator[LocalRepository]:
        url = self.url.replace("://", f"://{user.name}@") if user else self.url
        async with LocalRepository.clone(
            self.workdir,
            self.name,
            url,
            self.anonymizer,
            user=user,
            git_askpass=self.git_askpass,
        ) as repository:
            yield repository

    @contextlib.asynccontextmanager
    async def worktree(self, user: Optional[User] = None) -> AsyncIterator[Worktree]:
        async with self.clone(user) as repository:
            async with repository.worktree() as worktree:
                yield worktree

    async def __aenter__(self) -> CriticRepository:
        await self.__create()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.delete_on_exit:
            await self.__delete()


@pytest.fixture
async def critic_repo(
    request: Request,
    workdir: str,
    instance: Instance,
    api: API,
    websocket: WebSocket,
    git_askpass: str,
    admin: User,
    anonymizer: Anonymizer,
) -> AsyncIterator[CriticRepository]:
    async with CriticRepository(
        workdir,
        instance,
        api,
        websocket,
        git_askpass,
        admin,
        anonymizer,
        request.node.name,
        delete_on_exit=not request.config.getoption("--keep-data"),
    ) as repository:
        await websocket.expect(
            action="modified", resource_name="repositories", updates={"is_ready": True}
        )
        yield repository
