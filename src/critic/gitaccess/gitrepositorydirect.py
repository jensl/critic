# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import (
    Any,
    AsyncIterator,
    Collection,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

logger = logging.getLogger(__name__)

from . import (
    GitError,
    SHA1,
    as_sha1,
    git,
    FetchRangeOrder,
    GitRemoteRefs,
    FetchJob,
    RevlistOrder,
    RevlistFlag,
    StreamCommand,
)
from .gitobject import (
    ObjectType,
    asObjectType,
    GitObject,
    GitRawObject,
    GitCommit,
    GitTreeEntry,
)
from .gitrepositoryimpl import GitRepositoryImpl
from .giterror import (
    GitError,
    GitProcessError,
    GitReferenceError,
    GitFetchError,
)
from . import (
    GitRemoteRefs,
    FetchJob,
    FetchRangeOrder,
    RevlistFlag,
    RevlistOrder,
    StreamCommand,
)

from critic import base
from critic import textutils

RE_FULL_SHA1 = re.compile("^[0-9A-Fa-f]{40}$")
CATFILE_KEEPALIVE_SECONDS = 30


class _CatFileStopped(Exception):
    pass


class GitRepositoryDirect(GitRepositoryImpl):
    worktree_path: Optional[str]
    fetch_queue: Optional[asyncio.Queue[FetchJob]]

    def __init__(self, path: Optional[str]) -> None:
        self.__path = path
        self.worktree_path = None
        self.loop = asyncio.get_running_loop()
        self.fetch_queue = None
        self.fetch_failed = False
        self.fetch_cache: Dict[str, GitObject] = {}
        self.__environ = os.environ.copy()

    @property
    def is_direct(self) -> bool:
        return True

    @property
    def path(self) -> Optional[str]:
        if self.__path is None:
            return None
        return os.path.join(
            str(base.configuration()["paths.repositories"]), self.__path
        )

    @property
    def environ(self) -> Dict[str, str]:
        # assert self.fetch_queue is None, "catfile process already started"
        return self.__environ

    def set_environ(self, env: Mapping[str, str]) -> Mapping[str, str]:
        backup_env = self.__environ.copy()
        self.__environ.clear()
        self.__environ.update(env)
        return backup_env

    def set_author_details(self, name: str, email: str) -> None:
        self.__environ.update(GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email)

    def set_committer_details(self, name: str, email: str) -> None:
        self.__environ.update(GIT_COMMITTER_NAME=name, GIT_COMMITTER_EMAIL=email)

    def clear_user_details(self) -> None:
        self.__environ.pop("GIT_AUTHOR_NAME", None)
        self.__environ.pop("GIT_AUTHOR_EMAIL", None)
        self.__environ.pop("GIT_COMMITTER_NAME", None)
        self.__environ.pop("GIT_COMMITTER_EMAIL", None)

    def get_worktree_path(self) -> str:
        assert self.worktree_path
        return self.worktree_path

    def set_worktree_path(self, path: Optional[str]) -> None:
        self.worktree_path = path

    def start_catfile(self) -> None:
        path = self.path
        assert path

        self.fetch_queue = asyncio.Queue()

        async def process_job(
            process: asyncio.subprocess.Process, job: FetchJob
        ) -> GitObject:
            assert self.path

            object_id = job.object_id
            assert object_id
            sha1 = object_id.encode()

            stdin = process.stdin
            assert stdin
            stdin.write(b"%s\n" % sha1)

            stdout = process.stdout
            assert stdout
            header = await stdout.readline()

            if not header.startswith(sha1):
                raise GitFetchError.make(object_id, self.path, header.decode())

            _, object_type_bytes, size_bytes = header.split(b" ")
            object_type = asObjectType(object_type_bytes.decode("ascii"))

            if job.wanted_object_type is not None:
                if object_type != job.wanted_object_type:
                    raise GitFetchError.make(
                        object_id,
                        self.path,
                        "Wrong type of object: expected "
                        f"`{job.wanted_object_type}`, got `{object_type}`",
                    )

            data = await stdout.readexactly(int(size_bytes, base=10))

            return job.object_factory(object_id, object_type, data)

        async def run() -> None:
            assert self.fetch_queue

            process = await asyncio.create_subprocess_exec(
                git(),
                "cat-file",
                "--batch",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                cwd=path,
                loop=self.loop,
                env=self.__environ,
            )

            logger.debug("started `git cat-file` process: pid=%d", process.pid)

            while True:
                job: Optional[FetchJob]

                try:
                    job = await asyncio.wait_for(
                        self.fetch_queue.get(), CATFILE_KEEPALIVE_SECONDS
                    )
                except asyncio.TimeoutError:
                    job = None

                if job is None or job.object_id is None:
                    self.fetch_queue = None
                    logger.debug("stopping `git cat-file` process")
                    process.terminate()
                    await process.wait()
                    logger.debug("stopped `git cat-file` process")
                    if job:
                        job.future.set_exception(_CatFileStopped())
                    return

                try:
                    gitobject = await process_job(process, job)
                except Exception as error:
                    job.future.set_exception(error)
                else:
                    job.future.set_result(gitobject)

                stdout = process.stdout
                assert stdout
                await stdout.read(1)

        def run_done(future: "asyncio.Future[Any]") -> None:
            try:
                future.result()
            except Exception as error:
                logger.exception("Communication with `git cat-file` failed:")
                if self.fetch_queue:
                    fetch_queue = self.fetch_queue
                    self.fetch_queue = None
                    self.fetch_failed = True
                    try:
                        while True:
                            fetch_queue.get_nowait().future.set_exception(error)
                    except asyncio.QueueEmpty:
                        pass
            else:
                self.fetch_queue = None

        self.catfile_run = asyncio.ensure_future(run(), loop=self.loop)
        self.catfile_run.add_done_callback(run_done)

    def ensure_catfile(self) -> bool:
        if self.fetch_queue is False:
            return False
        if self.fetch_queue is None:
            self.start_catfile()
        return True

    async def stop_catfile(self) -> None:
        if self.fetch_queue:
            job = FetchJob(None)
            await self.fetch_queue.put(job)
            try:
                await job.future
            except _CatFileStopped:
                pass
            await self.catfile_run

    async def execute(
        self,
        *argv: str,
        stdin_mode: int = asyncio.subprocess.DEVNULL,
        cwd: Optional[str] = None,
        # env: Dict[str, str] = None,
    ) -> asyncio.subprocess.Process:
        if cwd is None:
            if self.worktree_path is not None:
                cwd = self.worktree_path
            else:
                cwd = self.path

        logger.debug("executing: `git %s` in %r", " ".join(argv), cwd)

        return await asyncio.create_subprocess_exec(
            git(),
            *argv,
            loop=self.loop,
            cwd=cwd,
            env=self.__environ,
            stdin=stdin_mode,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def run(
        self,
        *argv: str,
        stdin_data: Optional[Union[str, bytes]] = None,
        cwd: Optional[str] = None,
    ) -> bytes:
        if stdin_data is not None:
            stdin_mode = asyncio.subprocess.PIPE
            if isinstance(stdin_data, str):
                stdin_data = stdin_data.encode()
        else:
            stdin_mode = asyncio.subprocess.DEVNULL

        process = await self.execute(*argv, stdin_mode=stdin_mode, cwd=cwd)
        stdout, stderr = await process.communicate(stdin_data)

        assert process.returncode is not None

        logger.debug(
            "executed: `git %s` in %r [returncode=%d]",
            " ".join(argv),
            self.path,
            process.returncode,
        )

        if process.returncode != 0:
            raise GitProcessError.make(
                argv, self.path, process.returncode, stdout, stderr
            )

        return stdout

    async def version(self) -> Optional[str]:
        output = (await self.run("--version")).decode().strip()

        if output.startswith("git version "):
            return output[len("git version ") :]
        else:
            logger.warning("Unrecognized output from `git --version`: %r", output)

        return None

    async def repositories_dir(self) -> str:
        return str(base.configuration()["paths.repositories"])

    async def symbolicref(
        self, name: str, *, value: Optional[str] = None, delete: bool = False
    ) -> str:
        argv = ["symbolic-ref"]
        if delete:
            argv.append("--delete")
        argv.append(name)
        if value is not None:
            argv.append(value)
        return (await self.run(*argv)).decode().strip()

    async def revparse(
        self,
        ref: str,
        *,
        short: Optional[Union[bool, int]],
        object_type: Optional[ObjectType],
    ) -> str:
        assert self.path
        argv = ["rev-parse", "--quiet", "--verify"]
        if short:
            if short is True:
                argv.append("--short")
            else:
                argv.append("--short=%d" % short)
        if object_type is not None:
            ref += "^{%s}" % object_type
        argv.append(ref)
        try:
            output = await self.run(*argv)
        except GitProcessError as error:
            raise GitReferenceError.make(
                ref, self.path, error.stderr.decode() if error.stderr else ""
            )
        sha1 = output.decode().strip()
        if not RE_FULL_SHA1.match(sha1):
            raise GitError("Unexpected output from `git rev-parse`: %r" % output)
        return sha1

    async def revlist(
        self,
        include: Sequence[str],
        exclude: Sequence[str],
        *,
        symmetric: Optional[Tuple[str, str]],
        count: bool,
        paths: Collection[str],
        offset: Optional[int],
        limit: Optional[int],
        min_parents: Optional[int],
        max_parents: Optional[int],
        order: Optional[RevlistOrder],
        flags: Collection[RevlistFlag],
    ) -> Union[Sequence[SHA1], int]:
        argv = ["rev-list"]
        if count:
            argv.append("--count")
        if offset is not None:
            argv.append("--skip=%d" % offset)
        if limit is not None:
            argv.append("--max-count=%d" % limit)
        if min_parents is not None:
            argv.append("--min-parents=%d" % min_parents)
        if max_parents is not None:
            argv.append("--max-parents=%d" % max_parents)
        if order is not None:
            assert order in ("date", "author-date", "topo")
            argv.append("--%s-order" % order)
        argv.extend(f"--{flag}" for flag in flags)
        if symmetric is not None:
            argv.append(f"{symmetric[0]}...{symmetric[1]}")
        else:
            argv.extend(include)
            if exclude == ["--all"]:
                argv.extend(["--not", "--all"])
            elif exclude:
                argv.extend(f"^{ref}" for ref in exclude)
        output = await self.run(*argv)
        if count:
            return int(output.strip())
        sha1s = output.decode("ascii").splitlines()
        try:
            return [as_sha1(sha1) for sha1 in sha1s]
        except ValueError:
            raise GitError("Unexpected output from `git rev-list`: %r" % output)

    async def mergebase(self, *commits: str, is_ancestor: bool) -> Union[SHA1, bool]:
        argv = ["merge-base"]
        if is_ancestor:
            argv.append("--is-ancestor")
        argv.extend(commits)
        try:
            output = await self.run(*argv)
        except GitProcessError as error:
            if is_ancestor and error.returncode == 1:
                return False
            raise
        if is_ancestor:
            return True
        sha1 = output.decode().strip()
        try:
            return as_sha1(sha1)
        except ValueError:
            raise GitError("Unexpected output from `git merge-base`: %r" % output)

    async def lstree(
        self, ref: str, path: Optional[str] = None, *, long_format: bool = False
    ) -> Sequence[GitTreeEntry]:
        argv = ["ls-tree", "-z"]
        if long_format:
            argv.append("--long")
        argv.append(ref)
        if path:
            argv.append(path)
        output = await self.run(*argv)
        entries = []
        for entry in filter(None, output.rstrip(b"\0").split(b"\0")):
            information, _, name = entry.partition(b"\t")
            size: Optional[int]
            if long_format:
                mode, object_type, sha1, size_bytes = information.split()
                if size_bytes == b"-":
                    size = None
                else:
                    size = int(size_bytes, base=10)
            else:
                mode, object_type, sha1 = information.split()
                size = None
            entries.append(
                GitTreeEntry(
                    int(mode, base=8),
                    name,
                    as_sha1(sha1.decode("ascii")),
                    object_type=asObjectType(object_type.decode("ascii")),
                    size=size,
                )
            )
        return entries

    async def fetch(
        self,
        *object_ids: SHA1,
        include: Optional[Iterable[str]],
        exclude: Optional[Iterable[str]],
        order: FetchRangeOrder,
        skip: Optional[int],
        limit: Optional[int],
        wanted_object_type: Optional[ObjectType],
        object_factory: Optional[Type[GitObject]],
    ) -> AsyncIterator[Tuple[SHA1, Union[GitObject, GitFetchError]]]:
        if not self.ensure_catfile():
            raise GitFetchError.make(
                None, self.path, "failed to run `git cat-file` process"
            )

        assert self.fetch_queue

        if include is not None:
            assert not object_ids
            assert wanted_object_type in (None, "commit")
            assert object_factory in (None, GitRawObject, GitCommit)

            if object_factory is None:
                object_factory = GitCommit

            update_cache = object_factory == GitCommit

            format_spec = "%x00".join(
                ["%T:%P", "%an <%ae> %ad", "%cn <%ce> %cd", "%B", "", ""]
            )

            argv = ["rev-list", "--date=raw", "--format=" + format_spec]
            if order is not None:
                argv.append(f"--{order}-order")
            if skip is not None:
                argv.append(f"--skip={skip}")
            if limit is not None:
                argv.append(f"--max-count={limit}")
            argv.extend(str(ref) for ref in include)
            if exclude:
                argv.extend(f"^{ref}" for ref in exclude)
            process = await self.execute(*argv)

            stdout = process.stdout
            assert stdout

            while True:
                try:
                    header = (await stdout.readuntil(b"\n"))[:-1]
                except asyncio.IncompleteReadError as error:
                    if error.partial:
                        raise
                    break

                assert header.startswith(b"commit "), header
                sha1_bytes = header[7:]
                assert len(sha1_bytes) == 40

                custom = (await stdout.readuntil(b"\0\0"))[:-2]

                tree_parents, author, committer, message = custom.split(b"\0")
                tree, _, parents = tree_parents.partition(b":")

                git_object = object_factory.fromCommitItems(
                    sha1_bytes, tree, parents.split(), author, committer, message
                )

                yield git_object.sha1, git_object

                if update_cache:
                    self.fetch_cache[str(git_object)] = git_object

                linebreak = await stdout.readexactly(1)
                assert linebreak == b"\n"

            return

        job: Union[GitObject, FetchJob, str]
        jobs: List[Union[GitObject, FetchJob, str]] = []
        update_cache = object_factory == GitCommit

        for object_id in object_ids:
            if update_cache and object_id in self.fetch_cache:
                logger.debug("cached: %s", object_id)
                jobs.append(self.fetch_cache[object_id])
            else:
                logger.debug("fetch: %s", object_id)

                job = FetchJob(
                    object_id,
                    wanted_object_type=wanted_object_type,
                    object_factory=object_factory,
                )
                jobs.append(job)

                await self.fetch_queue.put(job)

        for object_id, job in zip(object_ids, jobs):
            if isinstance(job, str):
                logger.error("fetch failed: %s", job)
                yield object_id, GitFetchError(object_id, self.path, job)
            elif isinstance(job, GitCommit):
                yield object_id, job
            else:
                assert isinstance(job, FetchJob)
                try:
                    yield object_id, await job.future
                except GitError as error:
                    logger.exception("fetch failed")
                    yield object_id, GitFetchError(object_id, self.path, str(error))

    async def committree(
        self, tree: str, parents: Iterable[SHA1], message: str
    ) -> SHA1:
        assert "GIT_AUTHOR_NAME" in self.__environ
        argv = ["commit-tree", tree]
        for parent in parents:
            argv.extend(["-p", parent])
        output = await self.run(*argv, stdin_data=message)
        return as_sha1(output.decode().strip())

    async def foreachref(self, *, pattern: Optional[str] = None) -> Sequence[str]:
        argv = ["for-each-ref", "--format=%(refname)"]
        if pattern is not None:
            argv.append(pattern)
        output = await self.run(*argv)
        return output.decode().splitlines()

    async def updateref(
        self,
        name: str,
        *,
        old_value: Optional[SHA1] = None,
        new_value: Optional[SHA1] = None,
        create: bool = False,
        delete: bool = False,
    ) -> None:
        if create:
            command = "create "
        elif delete:
            command = "delete "
        else:
            command = "update "
        command += name + "\0"
        if new_value:
            command += new_value + "\0"
        if old_value:
            command += old_value + "\0"
        elif not (delete or create):
            command += "\0"
        logger.warning(f"{command=}")
        stdout = await self.run("update-ref", "--stdin", "-z", stdin_data=command)

    async def lsremote(
        self,
        url: str,
        *refs: str,
        include_heads: bool = False,
        include_tags: bool = False,
        include_refs: bool = False,
        include_symbolic_refs: bool = False,
    ) -> GitRemoteRefs:
        argv = []

        if include_heads:
            argv.append("--heads")
        if include_tags:
            argv.append("--tags")
        if include_refs:
            argv.append("--refs")
        if include_symbolic_refs:
            argv.append("--symref")

        argv.append(url)
        argv.extend(refs)

        normal_refs: Dict[str, SHA1] = {}
        symbolic_refs = {}

        output = await self.run("ls-remote", *argv)
        for line in output.decode().splitlines():
            if line.startswith("ref: "):
                refname, _, symrefname = line[len("ref: ") :].partition("\t")
                symbolic_refs[symrefname] = refname
            else:
                sha1, _, refname = line.partition("\t")
                normal_refs[refname] = as_sha1(sha1)

        return GitRemoteRefs(normal_refs, symbolic_refs)

    async def stream(
        self,
        command: StreamCommand,
        input_queue: "asyncio.Queue[bytes]",
        output_queue: "asyncio.Queue[bytes]",
        env: Optional[Mapping[str, str]],
    ) -> None:
        assert self.path

        logger.debug("executing: `git %s` in %r", command, self.path)

        argv = [git(), command]

        use_env = {**env} if env is not None else os.environ.copy()
        if command == "http-backend":
            use_env["GIT_PROJECT_ROOT"] = str(
                base.configuration()["paths.repositories"]
            )
        elif command in ("receive-pack", "upload-pack", "upload-archive"):
            argv.append(self.path)

        # logger.debug("argv: %r", argv)
        # logger.debug("env: %r", use_env)

        process = await asyncio.create_subprocess_exec(
            *argv,
            env=use_env,
            cwd=self.path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            loop=self.loop,
        )

        # logger.debug("pid: %d", process.pid)

        stderr: Optional[bytes] = None

        async def write_input() -> None:
            stdin = process.stdin
            assert stdin
            while True:
                data = await input_queue.get()
                # if data:
                #     logger.debug("received %d input bytes", len(data))
                # else:
                #     logger.debug("input queue closed")
                if not data:
                    stdin.close()
                    return
                stdin.write(data)

        async def read_output() -> None:
            stdout = process.stdout
            assert stdout
            while True:
                data = await stdout.read(65536)
                # if data:
                #     logger.debug("sending %d output bytes", len(data))
                # else:
                #     logger.debug("closing output queue")
                await output_queue.put(data)
                if not data:
                    return

        async def read_errors() -> bytes:
            stderr = process.stderr
            assert stderr
            return await stderr.read()

        [_, _, stderr, _] = await asyncio.gather(
            write_input(), read_output(), read_errors(), process.wait()
        )

        # logger.debug("returncode: %r", process.returncode)

        assert process.returncode is not None

        if process.returncode != 0:
            raise GitProcessError.make(
                [command], self.path, process.returncode, None, stderr
            )

    async def clone(self, url: str, *, bare: bool = True, mirror: bool = False) -> None:
        assert self.path
        assert not os.path.isdir(self.path)
        assert (bare or mirror) == self.path.endswith(".git")

        argv = ["clone"]
        if mirror:
            argv.append("--mirror")
        elif bare:
            argv.append("--bare")
        argv.extend([url, self.path])

        await self.run(*argv, cwd=str(base.configuration()["paths.home"]))

    async def close(self) -> None:
        logger.debug("closing repository")
        await self.stop_catfile()
