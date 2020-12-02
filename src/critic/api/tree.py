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

from typing import Awaitable, Callable, Protocol, Sequence, Optional, overload

from critic import api
from critic.api.apiobject import FunctionRef
from critic.gitaccess import SHA1


class Error(api.APIError):
    """Base exception for all errors related to the Tree class."""

    pass


class InvalidSHA1(Error):
    """Raised when an invalid tree SHA-1 is used"""

    def __init__(self, repository: api.repository.Repository, sha1: SHA1) -> None:
        super().__init__("Invalid tree SHA-1: %s in %s" % (sha1, repository.path))
        self.repository = repository
        self.sha1 = sha1


class PathNotFound(Error):
    """Raised when the path is not found in the given commit"""

    def __init__(self, commit: api.commit.Commit, path: str) -> None:
        super().__init__("Path not found: %r in %s" % (path, commit))
        self.commit = commit
        self.path = path


class NotADirectory(Error):
    """Raised when the path is not a directory in the given commit"""

    def __init__(self, commit: api.commit.Commit, path: str) -> None:
        super().__init__("Not a directory: %r in %s" % (path, commit))
        self.commit = commit
        self.path = path


class Tree(api.APIObject):
    """Representation of a Git tree object, i.e. a directory listing"""

    def __hash__(self) -> int:
        return hash((self.repository.id, self.sha1))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Tree)
            and self.repository == other.repository
            and self.sha1 == other.sha1
        )

    @property
    def repository(self) -> api.repository.Repository:
        """The repository containing this entry"""
        return self._impl.repository

    @property
    def sha1(self) -> SHA1:
        """The SHA-1 of this tree's Git object"""
        return self._impl.sha1

    class Entry(Protocol):
        """Representation of a single directory entry"""

        @property
        def tree(self) -> Tree:
            """The tree that this entry belongs to"""
            ...

        @property
        def mode(self) -> int:
            """The entry's mode as an integer"""
            ...

        @property
        def name(self) -> str:
            """The entry's name"""
            ...

        @property
        def sha1(self) -> SHA1:
            """The SHA-1 of the entry's content object"""
            ...

        @property
        def size(self) -> Optional[int]:
            """The size of the entry's content object"""
            ...

        @property
        def isDirectory(self) -> bool:
            """True if the entry represents a sub-directory"""
            ...

        @property
        def isSymbolicLink(self) -> bool:
            """True if the entry represents a symbolic link"""
            ...

        @property
        def isRegularFile(self) -> bool:
            """True if the entry represents a regular file"""
            ...

        @property
        def isSubModule(self) -> bool:
            """True if the entry represents a sub-module mount point"""
            ...

    @property
    def entries(self) -> Sequence[Tree.Entry]:
        """The entries of this directory


        The entries are returned as a list of Entry objects, ordered
        lexicographically by name."""
        return self._impl.getEntries(self)

    async def readLink(self, entry: Tree.Entry) -> str:
        assert entry.isSymbolicLink
        return await self._impl.readLink(entry)


@overload
async def fetch(*, repository: api.repository.Repository, sha1: SHA1) -> Tree:
    ...


@overload
async def fetch(*, commit: api.commit.Commit, path: str) -> Tree:
    ...


@overload
async def fetch(*, entry: Tree.Entry) -> Tree:
    ...


async def fetch(
    *,
    repository: Optional[api.repository.Repository] = None,
    sha1: Optional[SHA1] = None,
    commit: Optional[api.commit.Commit] = None,
    path: Optional[str] = None,
    entry: Optional[Tree.Entry] = None
) -> Tree:
    if repository:
        critic = repository.critic
    elif commit:
        critic = commit.critic
    else:
        assert entry and entry.isDirectory
        critic = entry.tree.critic

    return await fetchImpl.get()(critic, repository, sha1, commit, path, entry)


resource_name = "trees"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.repository.Repository],
            Optional[SHA1],
            Optional[api.commit.Commit],
            Optional[str],
            Optional[Tree.Entry],
        ],
        Awaitable[Tree],
    ]
] = FunctionRef()
