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
import contextlib
import logging
import os
import re
import tempfile
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Collection,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

logger = logging.getLogger(__name__)

from . import (
    SHA1,
    GitRemoteRefs,
    FetchJob,
    FetchRangeOrder,
    RevlistFlag,
    RevlistOrder,
    StreamCommand,
)
from .giterror import (
    GitError,
    GitRepositoryError,
    GitProcessError,
    GitReferenceError,
    GitFetchError,
)
from .gitobject import ObjectType, GitObject, GitRawObject, GitTreeEntry
from .gitrepositoryimpl import GitRepositoryImpl
from critic import base


def resolve_object_factory(wanted_object_type: Optional[ObjectType]) -> Type[GitObject]:
    if wanted_object_type is None:
        return GitRawObject
    else:
        return GitObject.factory_for[wanted_object_type]


def is_valid_object_type(object_type: ObjectType) -> bool:
    return object_type is None or object_type in GitRepository.OBJECT_TYPES


GitObjectType = TypeVar("GitObjectType", bound=GitObject)


class GitRepository:
    OBJECT_TYPES: FrozenSet[ObjectType] = frozenset({"blob", "commit", "tag", "tree"})

    def __init__(self, impl: GitRepositoryImpl):
        self.__impl = impl

    @property
    def path(self) -> Optional[str]:
        return self.__impl.path

    @property
    def environ(self) -> Mapping[str, str]:
        assert isinstance(self.__impl, GitRepositoryDirect)
        return self.__impl.environ

    @contextlib.contextmanager
    def with_environ(
        self, env: Mapping[str, str] = None, /, **overrides: str
    ) -> Iterator[GitRepository]:
        if env is None:
            env = {**self.environ, **overrides}
        backup_env = self.__impl.set_environ(env)
        try:
            yield self
        finally:
            self.__impl.set_environ(backup_env)

    async def version(self) -> Optional[str]:
        return await self.__impl.version()

    async def repositories_dir(self) -> str:
        return await self.__impl.repositories_dir()

    @overload
    async def symbolicref(self, name: str) -> str:
        ...

    @overload
    async def symbolicref(self, name: str, *, value: str) -> str:
        ...

    @overload
    async def symbolicref(self, name: str, *, delete: Literal[True]) -> str:
        ...

    async def symbolicref(
        self, name: str, *, value: str = None, delete: bool = False
    ) -> str:
        return await self.__impl.symbolicref(name, value=value, delete=delete)

    @overload
    async def revparse(self, ref: str, *, object_type: ObjectType = None) -> SHA1:
        ...

    @overload
    async def revparse(
        self,
        ref: str,
        *,
        short: Union[Literal[True], int],
        object_type: ObjectType = None,
    ) -> str:
        ...

    async def revparse(
        self,
        ref: str,
        *,
        short: Union[Literal[True], int] = None,
        object_type: ObjectType = None,
    ) -> Union[SHA1, str]:
        return await self.__impl.revparse(ref, object_type=object_type, short=short)

    @overload
    async def revlist(
        self,
        include: Iterable[str],
        exclude: Iterable[str] = (),
        *,
        paths: Iterable[str] = None,
        offset: int = None,
        limit: int = None,
        min_parents: int = None,
        max_parents: int = None,
        order: RevlistOrder = None,
        flags: Collection[RevlistFlag] = set(),
    ) -> Sequence[SHA1]:
        ...

    @overload
    async def revlist(
        self,
        include: Iterable[str],
        exclude: Iterable[str] = (),
        *,
        count: Literal[True],
        paths: Iterable[str] = None,
        offset: int = None,
        limit: int = None,
        min_parents: int = None,
        max_parents: int = None,
        order: RevlistOrder = None,
        flags: Collection[RevlistFlag] = set(),
    ) -> int:
        ...

    @overload
    async def revlist(
        self,
        *,
        symmetric: Tuple[str, str],
        paths: Iterable[str] = None,
        offset: int = None,
        limit: int = None,
        min_parents: int = None,
        max_parents: int = None,
        order: RevlistOrder = None,
        flags: Collection[RevlistFlag] = set(),
    ) -> Sequence[SHA1]:
        ...

    @overload
    async def revlist(
        self,
        *,
        symmetric: Tuple[str, str],
        count: Literal[True],
        paths: Iterable[str] = None,
        offset: int = None,
        limit: int = None,
        min_parents: int = None,
        max_parents: int = None,
        order: RevlistOrder = None,
        flags: Collection[RevlistFlag] = set(),
    ) -> int:
        ...

    async def revlist(
        self,
        include: Iterable[str] = (),
        exclude: Iterable[str] = (),
        *,
        symmetric: Tuple[str, str] = None,
        count: Literal[True] = None,
        paths: Iterable[str] = None,
        offset: int = None,
        limit: int = None,
        min_parents: int = None,
        max_parents: int = None,
        order: RevlistOrder = None,
        flags: Collection[RevlistFlag] = set(),
    ) -> Union[Sequence[SHA1], int]:
        assert self.path
        return await self.__impl.revlist(
            list(include),
            list(exclude),
            symmetric=symmetric,
            count=bool(count),
            paths=list(paths) if paths else [],
            offset=offset,
            limit=limit,
            min_parents=min_parents,
            max_parents=max_parents,
            order=order,
            flags=sorted(flags),
        )

    @overload
    async def mergebase(self, *commits: str) -> SHA1:
        ...

    @overload
    async def mergebase(
        self, ancestor: str, descendant: str, /, *, is_ancestor: Literal[True]
    ) -> bool:
        ...

    async def mergebase(
        self, *commits: str, is_ancestor: Literal[True] = None
    ) -> Union[SHA1, bool]:
        assert self.path
        assert is_ancestor is None or isinstance(is_ancestor, bool)
        assert is_ancestor is None or len(commits) == 2
        return await self.__impl.mergebase(*commits, is_ancestor=bool(is_ancestor))

    async def lstree(
        self, ref: str, path: str = None, *, long_format: bool = False
    ) -> Sequence[GitTreeEntry]:
        assert self.path
        return await self.__impl.lstree(ref, path, long_format=long_format)

    # FIXME: mypy appears to become confused with these overload definitions.

    # @overload
    # async def fetch(
    #     self,
    #     *object_ids: str,
    #     order: Literal["date", "topo"] = "date",
    #     wanted_object_type: ObjectType = None,
    #     object_factory: Type[GitObject] = None,
    # ) -> AsyncIterator[Tuple[str, GitObject]]:
    #     ...

    # @overload
    # async def fetch(
    #     self,
    #     *,
    #     include: Iterable[str],
    #     exclude: Iterable[str] = None,
    #     order: Literal["date", "topo"] = "date",
    #     skip: int = None,
    #     limit: int = None,
    #     wanted_object_type: ObjectType = None,
    #     object_factory: Type[GitObject] = None,
    # ) -> AsyncIterator[Tuple[str, GitObject]]:
    #     ...

    async def fetch(
        self,
        *object_ids: SHA1,
        include: Iterable[str] = None,
        exclude: Iterable[str] = None,
        order: Optional[FetchRangeOrder] = None,
        skip: int = None,
        limit: int = None,
        wanted_object_type: ObjectType = None,
        object_factory: Type[GitObject] = None,
    ) -> AsyncIterator[Tuple[SHA1, Union[GitObject, GitFetchError]]]:
        assert self.path
        async for item in self.__impl.fetch(
            *object_ids,
            include=include,
            exclude=exclude,
            order=order or "date",
            skip=skip,
            limit=limit,
            wanted_object_type=wanted_object_type,
            object_factory=object_factory,
        ):
            yield item

    @overload
    async def fetchone(
        self, object_id: SHA1, *, wanted_object_type: ObjectType = None,
    ) -> GitObject:
        ...

    @overload
    async def fetchone(
        self,
        object_id: SHA1,
        *,
        object_factory: Type[GitObjectType],
        wanted_object_type: ObjectType = None,
    ) -> GitObjectType:
        ...

    async def fetchone(
        self,
        object_id: SHA1,
        *,
        wanted_object_type: ObjectType = None,
        object_factory: Type[GitObject] = None,
    ) -> GitObject:
        async for object_id, gitobject in self.fetch(
            object_id,
            wanted_object_type=wanted_object_type,
            object_factory=object_factory,
        ):
            if isinstance(gitobject, GitFetchError):
                raise gitobject
            return gitobject
        else:
            raise Exception("expected an object")

    async def fetchall(
        self,
        *object_ids: SHA1,
        wanted_object_type: ObjectType = None,
        object_factory: Type[GitObject] = None,
    ) -> Sequence[GitObject]:
        result: List[GitObject] = []
        async for object_id, gitobject in self.fetch(
            *object_ids,
            wanted_object_type=wanted_object_type,
            object_factory=object_factory,
        ):
            assert object_id == object_ids[len(result)]
            if isinstance(gitobject, GitFetchError):
                raise gitobject
            result.append(gitobject)
        assert len(result) == len(object_ids)
        return result

    async def committree(
        self, tree: SHA1, parents: Iterable[SHA1], message: str
    ) -> SHA1:
        assert self.path
        assert isinstance(self, GitRepositoryDirect)
        message = message.strip()
        assert message
        return await self.__impl.committree(tree, parents, message)

    async def foreachref(self, *, pattern: str = None) -> Sequence[str]:
        assert self.path
        return await self.__impl.foreachref(pattern=pattern)

    @overload
    async def updateref(
        self, name: str, *, old_value: SHA1 = None, new_value: SHA1
    ) -> None:
        ...

    @overload
    async def updateref(
        self, name: str, *, new_value: SHA1, create: Literal[True]
    ) -> None:
        ...

    @overload
    async def updateref(
        self, name: str, *, old_value: SHA1 = None, delete: Literal[True]
    ) -> None:
        ...

    async def updateref(
        self,
        name: str,
        *,
        old_value: SHA1 = None,
        new_value: SHA1 = None,
        create: Literal[True] = None,
        delete: Literal[True] = None,
    ) -> None:
        assert self.path
        assert name == "HEAD" or name.startswith("refs/")
        await self.__impl.updateref(
            name,
            old_value=old_value,
            new_value=new_value,
            create=bool(create),
            delete=bool(delete),
        )

    async def lsremote(
        self,
        url: str,
        *refs: str,
        include_heads: bool = False,
        include_tags: bool = False,
        include_refs: bool = False,
        include_symbolic_refs: bool = False,
    ) -> GitRemoteRefs:
        return await self.__impl.lsremote(
            url,
            *refs,
            include_heads=include_heads,
            include_tags=include_tags,
            include_refs=include_refs,
            include_symbolic_refs=include_symbolic_refs,
        )

    async def stream(
        self,
        command: StreamCommand,
        input_queue: "asyncio.Queue[bytes]",
        output_queue: "asyncio.Queue[bytes]",
        env: Mapping[str, str] = None,
    ) -> None:
        assert self.path
        await self.__impl.stream(command, input_queue, output_queue, env)

    async def clone(self, url: str, *, bare: bool = True, mirror: bool = False) -> None:
        assert self.path
        assert isinstance(self.__impl, GitRepositoryDirect)
        await self.__impl.clone(url, bare=bare, mirror=mirror)

    async def close(self) -> None:
        await self.__impl.close()

    def set_author_details(self, name: str, email: str) -> None:
        assert isinstance(self.__impl, GitRepositoryDirect)
        self.__impl.set_author_details(name, email)

    def set_committer_details(self, name: str, email: str) -> None:
        assert isinstance(self.__impl, GitRepositoryDirect)
        self.__impl.set_committer_details(name, email)

    def set_user_details(self, name: str, email: str) -> None:
        self.set_author_details(name, email)
        self.set_committer_details(name, email)

    def clear_user_details(self) -> None:
        assert isinstance(self.__impl, GitRepositoryDirect)
        self.__impl.clear_user_details()

    def set_worktree_path(self, path: Optional[str]) -> None:
        assert isinstance(self.__impl, GitRepositoryDirect)
        self.__impl.set_worktree_path(path)

    async def run(
        self, *argv: str, stdin_data: Union[str, bytes] = None, cwd: str = None
    ) -> bytes:
        assert isinstance(self.__impl, GitRepositoryDirect)
        return await self.__impl.run(*argv, stdin_data=stdin_data, cwd=cwd)

    @contextlib.asynccontextmanager
    async def worktree(
        self, commit: str, new_branch: str = None, detach: bool = False
    ) -> AsyncIterator[GitRepository]:
        assert isinstance(self.__impl, GitRepositoryDirect)

        worktrees_dir = os.path.join(
            str(base.configuration()["paths.home"]), "worktrees"
        )
        if not os.path.isdir(worktrees_dir):
            os.mkdir(worktrees_dir, 0o700)

        argv = ["worktree", "add"]
        if new_branch:
            argv.extend(["-b", str(new_branch)])
        elif detach:
            argv.append("--detach")

        try:
            with tempfile.TemporaryDirectory(dir=worktrees_dir) as worktree_dir:
                await self.run(*argv, worktree_dir, str(commit))
                self.set_worktree_path(worktree_dir)
                yield self
        finally:
            self.set_worktree_path(None)
            self.run("worktree", "prune")

    @staticmethod
    def direct(path: str = None, allow_missing: bool = False) -> GitRepository:
        direct = GitRepositoryDirect(path)
        if not allow_missing and path and not os.path.isdir(direct.path):
            raise GitRepositoryError(f"Repository not found: {path}")
        return GitRepository(direct)

    async def __aenter__(self) -> GitRepository:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        return None


from .gitrepositorydirect import GitRepositoryDirect
