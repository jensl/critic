import asyncio
import os
from typing import (
    AsyncIterator,
    Collection,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    Union,
)

from . import (
    GitFetchError,
    GitObject,
    GitRemoteRefs,
    GitTreeEntry,
    ObjectType,
    RevlistFlag,
    RevlistOrder,
    SHA1,
    StreamCommand,
    FetchRangeOrder,
)


class GitRepositoryImpl(Protocol):
    @property
    def path(self) -> Optional[str]:
        ...

    @property
    def environ(self) -> Mapping[str, str]:
        ...

    def set_environ(self, env: Mapping[str, str]) -> Mapping[str, str]:
        ...

    async def version(self) -> Optional[str]:
        ...

    async def repositories_dir(self) -> str:
        ...

    def set_author_details(self, name: str, email: str) -> None:
        ...

    def set_committer_details(self, name: str, email: str) -> None:
        ...

    def clear_user_details(self) -> None:
        ...

    def set_worktree_path(self, path: Optional[str]) -> None:
        ...

    async def symbolicref(
        self, name: str, *, value: str = None, delete: bool = False
    ) -> str:
        ...

    async def revparse(
        self,
        ref: str,
        *,
        short: Optional[Union[bool, int]],
        object_type: Optional[ObjectType],
    ) -> str:
        ...

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
        ...

    async def mergebase(self, *commits: str, is_ancestor: bool) -> Union[SHA1, bool]:
        ...

    async def lstree(
        self, ref: str, path: str = None, *, long_format: bool = False
    ) -> Sequence[GitTreeEntry]:
        ...

    def fetch(
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
        ...

    async def committree(self, tree: str, parents: Iterable[str], message: str) -> str:
        ...

    async def foreachref(self, *, pattern: str = None) -> Sequence[str]:
        ...

    async def updateref(
        self,
        name: str,
        *,
        old_value: SHA1 = None,
        new_value: SHA1 = None,
        create: bool = False,
        delete: bool = False,
    ) -> None:
        ...

    async def lsremote(
        self,
        url: str,
        *refs: str,
        include_heads: bool = False,
        include_tags: bool = False,
        include_refs: bool = False,
        include_symbolic_refs: bool = False,
    ) -> GitRemoteRefs:
        ...

    async def stream(
        self,
        command: StreamCommand,
        input_queue: "asyncio.Queue[bytes]",
        output_queue: "asyncio.Queue[bytes]",
        env: Optional[Mapping[str, str]],
    ) -> None:
        ...

    async def clone(self, url: str, *, bare: bool = True, mirror: bool = False) -> None:
        ...

    async def close(self) -> None:
        ...
