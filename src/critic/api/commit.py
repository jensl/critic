# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import datetime
from typing import (
    Awaitable,
    Callable,
    Optional,
    Sequence,
    Protocol,
    Iterable,
    Literal,
    Tuple,
    overload,
)

from critic import api
from critic import gitaccess
from critic.api.apiobject import FunctionRef
from critic.gitaccess import SHA1


class Error(api.APIError, object_type="commit"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid commit id is used"""

    pass


class InvalidSHA1(api.InvalidItemError, Error, item_type="commit SHA-1"):
    """Raised when a given SHA-1 is invalid as a commit reference"""

    pass


class NotAFile(Error):
    """Raised when attempting to access a non-file as a file"""

    def __init__(self, path: str) -> None:
        super().__init__("Path is not a file: %s" % path)
        self.path = path


class Commit(api.APIObject):
    """Representation of a Git commit"""

    def __str__(self) -> str:
        return self.sha1

    def __repr__(self) -> str:
        return "Commit(id=%d, sha1=%s, summary=%r)" % (self, self, self.summary)

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    @property
    def id(self) -> int:
        """The commit's unique database id"""
        return self._impl.id

    @property
    def repository(self) -> api.repository.Repository:
        """The repository containing the commit"""
        return self._impl.repository

    @property
    def sha1(self) -> SHA1:
        """The commit's full 40 character SHA-1"""
        return self._impl.sha1

    @property
    def tree(self) -> SHA1:
        """The SHA-1 of the tree object referenced by the commit"""
        return self._impl.tree

    @property
    def summary(self) -> str:
        """The commit's single-line summary

        This is the first line of the commit message, unless that line starts
        with 'fixup!' or 'squash!', in which case the returned summary is the
        first non-empty line after that, with '[fixup] ' or '[squash] '
        prepended.  If there is no such non-empty line, the returned summary
        is just '[fixup]' or '[squash]'."""
        return self._impl.getSummary()

    @property
    def message(self) -> str:
        """The commit's full commit message"""
        return self._impl.low_level.message

    @property
    def is_merge(self) -> bool:
        """True if this commit has more than one parent"""
        return self._impl.isMerge()

    @property
    async def parents(self) -> Tuple[Commit]:
        """The commit's parents

        The return value is a list of api.Commit objects."""
        return await self._impl.getParents()

    @property
    def low_level(self) -> gitaccess.GitCommit:
        """Low-level representation of this commit

        The representation is returned as a gitaccess.GitCommit object. This
        representation should typically not be used directly."""
        return self._impl.low_level

    @property
    async def description(self) -> CommitDescription:
        """A "friendly" description of the commit

        The description is returned as an CommitDescription object."""
        return await self._impl.getDescription(self)

    class UserAndTimestamp(Protocol):
        """Representation of the author or committer meta-data of a commit"""

        @property
        def name(self) -> str:
            ...

        @property
        def email(self) -> str:
            ...

        @property
        def timestamp(self) -> datetime.datetime:
            ...

    @property
    def author(self) -> UserAndTimestamp:
        """The commit's "author" meta-data"""
        return self._impl.getAuthor(self.critic)

    @property
    def committer(self) -> UserAndTimestamp:
        """The commit's "committer" meta-data"""
        return self._impl.getCommitter(self.critic)

    def isParentOf(self, child: Commit) -> bool:
        """Return True if |self| is one of |child|'s parents

        Using this is more efficient than checking if |self| is in the list
        returned by |child.parents|."""
        assert isinstance(child, Commit)
        return self._impl.isParentOf(child)

    async def isAncestorOf(self, commit: Commit) -> bool:
        """Return True if |self| is an ancestor of |commit|

        Also return True if |self| is |commit|, meaning a commit is considered
        an ancestor of itself."""
        assert isinstance(commit, Commit)
        return await self._impl.isAncestorOf(commit)

    class FileInformation(Protocol):
        """Basic information about a file in a commit"""

        @property
        def file(self) -> api.file.File:
            ...

        @property
        def mode(self) -> int:
            ...

        @property
        def sha1(self) -> SHA1:
            ...

        @property
        def size(self) -> int:
            ...

    async def getFileInformation(
        self, file: api.file.File
    ) -> Optional[FileInformation]:
        """Look up information about a file in the commit

        The entry is returned as an Commit.FileInformation object, or None if
        the path was not found in the commit's tree. If the path is found but
        is not a blob (e.g. because it's a directory), NotAFile is raised."""
        return await self._impl.getFileInformation(file)

    async def getFileContents(self, file: api.file.File) -> Optional[bytes]:
        """Fetch the blob (contents) of a file in the commit

        The return value is a `bytes` value, or None if the path was not
        found in the commit's tree. If the path is found but is not a blob
        (e.g. because it is a directory), NotAFile is raised."""
        return await self._impl.getFileContents(file)

    async def getFileLines(self, file: api.file.File) -> Optional[Sequence[str]]:
        """Fetch the lines of a file in the commit

        Much like getFileContents(), but splits the returned string into a
        list of strings in a consistent way that matches how other parts of
        Critic treats line breaks, and thus compatible with stored line
        numbers.

        Note: commit.getFileContents(...).splitlines() is *not* correct!"""
        return await self._impl.getFileLines(file)


class CommitDescription(Protocol):
    """A "friendly" description of a commit"""

    @property
    def commit(self) -> Commit:
        """The described commit"""
        ...

    @property
    def branch(self) -> Optional[api.branch.Branch]:
        """The most significant branch containing the commit, or None

        The branch is returned as an api.branch.Branch object.

        Typically, a branch is counted as more significant than another if it
        was created in Critic's repository earlier."""
        ...

    # @property
    # async def tag(self) -> Optional[api.tag.Tag]:
    #     """The oldest tag that points directly at the commit, or None

    #        The tag is returned as an api.tag.Tag object."""
    #     return await self._impl.getTag(self.critic)


@overload
async def fetch(repository: api.repository.Repository, commit_id: int, /) -> Commit:
    ...


@overload
async def fetch(repository: api.repository.Repository, /, *, sha1: SHA1) -> Commit:
    ...


@overload
async def fetch(repository: api.repository.Repository, /, *, ref: str) -> Commit:
    ...


async def fetch(
    repository: api.repository.Repository,
    commit_id: Optional[int] = None,
    /,
    *,
    sha1: Optional[SHA1] = None,
    ref: Optional[str] = None,
) -> Commit:
    """Fetch a Git commit from the given repository

    The commit can be identified by its unique (internal) database id, its
    SHA-1 (full 40 character string) or by an arbitrary ref that resolves to
    a commit object (possibly via tag objects) when given to the
    'git rev-parse' command."""
    return await fetchImpl.get()(repository, commit_id, sha1, ref)


@overload
async def fetchMany(
    repository: api.repository.Repository, commit_ids: Optional[Iterable[int]] = None, /
) -> Sequence[Commit]:
    ...


@overload
async def fetchMany(
    repository: api.repository.Repository, /, *, sha1s: Iterable[SHA1]
) -> Sequence[Commit]:
    ...


@overload
async def fetchMany(
    repository: api.repository.Repository,
    /,
    *,
    low_levels: Iterable[gitaccess.GitCommit],
) -> Sequence[Commit]:
    ...


async def fetchMany(
    repository: api.repository.Repository,
    commit_ids: Optional[Iterable[int]] = None,
    /,
    *,
    sha1s: Optional[Iterable[SHA1]] = None,
    low_levels: Optional[Iterable[gitaccess.GitCommit]] = None,
) -> Sequence[Commit]:
    """Fetch multiple Git commits from the given repository

    The commits can be identified by their unique (internal) database ids, or
    by their SHA-1s (full 40 character strings.)"""
    return await fetchManyImpl.get()(repository, commit_ids, sha1s, low_levels)


Order = Literal["date", "topo"]


async def fetchRange(
    *,
    from_commit: Optional[api.commit.Commit] = None,
    to_commit: api.commit.Commit,
    order: Order = "date",
    offset: Optional[int] = None,
    count: Optional[int] = None,
) -> api.commitset.CommitSet:
    """Fetch a range of Git commits

    If `from_commit` is not None, all ancestors of `to_commit` that are
    descendants of `from_commit` are returned.

    If `from_commit` is None, all ancestors of `to_commit` are returned.

    Note: `to_commit` is always included in the result. `from_commit` is
          never included in the result.

    If `order` is "date", the commits are returned in reverse chronological
    order (but always children before their parents.) If `order` is "topo",
    commits are primarily ordered such that children immediately preceed
    their parents. (See documentation for --date-order/--topo-order in
    git-rev-list(1).)

    If `offset` is not None, the first `offset` commits are skipped. If
    `count` is not None, at most `count` commits are returned.

    The return value is an api.commitset.CommitSet object."""
    assert from_commit is None or from_commit.repository == to_commit.repository
    assert offset is None or offset >= 0
    assert count is None or count > 0

    return await fetchRangeImpl.get()(from_commit, to_commit, order, offset, count)


async def prefetch(
    repository: api.repository.Repository, commit_ids: Iterable[int]
) -> None:
    """Prefetch Git commits from the given repository"""
    await prefetchImpl.get()(repository, list(commit_ids))


resource_name = table_name = "commits"


fetchImpl: FunctionRef[
    Callable[
        [
            api.repository.Repository,
            Optional[int],
            Optional[SHA1],
            Optional[str],
        ],
        Awaitable[Commit],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [
            api.repository.Repository,
            Optional[Iterable[int]],
            Optional[Iterable[SHA1]],
            Optional[Iterable[gitaccess.GitCommit]],
        ],
        Awaitable[Sequence[Commit]],
    ]
] = FunctionRef()
fetchRangeImpl: FunctionRef[
    Callable[
        [
            Optional[api.commit.Commit],
            api.commit.Commit,
            Order,
            Optional[int],
            Optional[int],
        ],
        Awaitable[api.commitset.CommitSet],
    ]
] = FunctionRef()
prefetchImpl: FunctionRef[
    Callable[[api.repository.Repository, Sequence[int]], Awaitable[None]]
] = FunctionRef()
