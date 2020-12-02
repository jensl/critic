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
from typing import Tuple, Optional, Sequence, Any

logger = logging.getLogger(__name__)

from .apiobject import APIObject
from critic import api
from critic.api import tree as public
from critic import gitaccess
from critic import textutils
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


WrapperType = api.tree.Tree
ArgumentsType = Tuple[api.repository.Repository, SHA1, Sequence[gitaccess.GitTreeEntry]]
CacheKeyType = Tuple[int, SHA1]


class Tree(APIObject[WrapperType, ArgumentsType, CacheKeyType]):
    wrapper_class = api.tree.Tree

    __entries: Optional[Sequence[api.tree.Tree.Entry]]

    def __init__(self, args: ArgumentsType):
        (self.repository, self.sha1, self.__low_entries) = args
        self.__entries = None

    @staticmethod
    def cacheKey(wrapper: WrapperType) -> CacheKeyType:
        return (wrapper.repository.id, wrapper.sha1)

    @classmethod
    def makeCacheKey(cls, args: ArgumentsType) -> CacheKeyType:
        repository, sha1, _ = args
        return (repository.id, sha1)

    @staticmethod
    def fetchCacheKey(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[api.critic.Critic, Optional[CacheKeyType]]:
        repository: Optional[api.repository.Repository]
        sha1: Optional[SHA1]
        commit: Optional[api.commit.Commit]
        entry: Optional[api.tree.Tree.Entry]
        repository, sha1, commit, _, entry = args
        if repository is not None:
            assert sha1 is not None
            return critic, (repository.id, sha1)
        elif commit is not None:
            return critic, None
        else:
            assert entry is not None
            return critic, (entry.tree.repository.id, entry.sha1)

    def getEntries(self, wrapper: WrapperType) -> Sequence[api.tree.Tree.Entry]:
        if self.__entries is None:
            self.__entries = sorted(
                (
                    Entry(
                        wrapper,
                        low_entry.mode,
                        low_entry.name,
                        low_entry.sha1,
                        low_entry.size,
                    )
                    for low_entry in self.__low_entries
                ),
                key=lambda entry: entry.name,
            )
        return self.__entries

    async def readLink(self, entry: api.tree.Tree.Entry) -> str:
        contents = await self.repository.getFileContents(sha1=entry.sha1)
        assert contents is not None
        return textutils.decode(contents)


@public.fetchImpl
@Tree.cached
async def fetch(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    sha1: Optional[SHA1],
    commit: Optional[api.commit.Commit],
    path: Optional[str],
    entry: Optional[api.tree.Tree.Entry],
) -> WrapperType:
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
    assert repository is not None
    assert sha1 is not None

    try:
        entries = await repository.low_level.lstree(sha1, long_format=True)
    except gitaccess.GitFetchError:
        raise api.tree.InvalidSHA1(repository, sha1)

    return await Tree.makeOne(repository.critic, values=(repository, sha1, entries))
