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

import logging
import stat
from dataclasses import dataclass
from typing import Collection, Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from .apiobject import APIObjectImpl
from critic import api
from critic.api import tree as public
from critic.api.apiobject import Actual
from critic import gitaccess
from critic.gitaccess import SHA1


@dataclass
class Entry:
    __tree: api.tree.Tree
    __mode: int
    __name: str
    __sha1: SHA1
    __size: Optional[int]

    @property
    def tree(self) -> api.tree.Tree:
        return self.__tree

    @property
    def mode(self) -> int:
        return self.__mode

    @property
    def name(self) -> str:
        return self.__name

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    @property
    def size(self) -> Optional[int]:
        return self.__size

    @property
    def isDirectory(self) -> bool:
        return stat.S_ISDIR(self.mode)

    @property
    def isSymbolicLink(self) -> bool:
        return stat.S_ISLNK(self.mode)

    @property
    def isRegularFile(self) -> bool:
        return stat.S_ISREG(self.mode)

    @property
    def isSubModule(self) -> bool:
        return (self.mode & 0o777000) == 0o160000


PublicType = public.Tree
CacheKeyType = Tuple[int, SHA1]


class Tree(PublicType, APIObjectImpl):
    wrapper_class = api.tree.Tree

    __entries: Optional[Sequence[api.tree.Tree.Entry]]

    def __init__(
        self,
        repository: api.repository.Repository,
        decode: api.repository.Decode,
        sha1: SHA1,
        low_entries: Sequence[gitaccess.GitTreeEntry],
    ):
        super().__init__(repository.critic)
        self.__repository = repository
        self.__decode = decode
        self.__sha1 = sha1
        self.__low_entries = low_entries
        self.__entries = None

    def __hash__(self) -> int:
        return hash((self.__repository, self.__sha1))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Tree)
            and self.__repository == other.__repository
            and self.__sha1 == other.__sha1
        )

    def getCacheKeys(self) -> Collection[object]:
        return ((self.__repository, self.__sha1),)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def repository(self) -> api.repository.Repository:
        return self.__repository

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    @property
    def entries(self) -> Sequence[api.tree.Tree.Entry]:
        if self.__entries is None:
            self.__entries = sorted(
                (
                    Entry(
                        self,
                        low_entry.mode,
                        self.__decode.path(low_entry.name),
                        low_entry.sha1,
                        low_entry.size,
                    )
                    for low_entry in self.__low_entries
                ),
                key=lambda entry: entry.name,
            )
        return self.__entries

    async def readLink(self, entry: PublicType.Entry) -> str:
        contents = await self.__repository.getFileContents(sha1=entry.sha1)
        assert contents is not None
        return self.__decode.path(contents)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    sha1: Optional[SHA1],
    commit: Optional[api.commit.Commit],
    path: Optional[str],
    entry: Optional[api.tree.Tree.Entry],
) -> PublicType:
    if commit is not None:
        assert path is not None
        repository = commit.repository
        if not path or path == "/":
            sha1 = commit.tree
        else:
            entries = await repository.low_level.lstree(commit.sha1, path.rstrip("/"))
            if not entries:
                raise api.tree.PathNotFound(commit, path)
            logger.debug("entries=%r", entries)
            if not entries[0].isdir():
                raise api.tree.NotADirectory(commit, path)
            sha1 = entries[0].sha1
    elif entry is not None:
        repository = entry.tree.repository
        sha1 = entry.sha1
    assert repository is not None and sha1 is not None

    try:
        entries = await repository.low_level.lstree(sha1, long_format=True)
    except gitaccess.GitFetchError:
        raise api.tree.InvalidSHA1(repository, sha1)

    return Tree.storeOne(
        Tree(repository, await repository.getDecode(commit), sha1, entries)
    )
