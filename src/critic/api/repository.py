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
from abc import abstractmethod

import re
from typing import (
    Awaitable,
    Callable,
    Collection,
    ContextManager,
    Optional,
    Sequence,
    Literal,
    Union,
    Iterable,
    Protocol,
    TypeVar,
    overload,
)

from critic import api
from critic import gitaccess
from critic.api.apiobject import FunctionRef
from critic.gitaccess import SHA1, ObjectType

RE_SHA1 = re.compile("^[0-9A-Fa-f]{40}$")

T = TypeVar("T")


class Error(api.APIError, object_type="repository"):
    """Base exception for all errors related to the Repository class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid repository id is used"""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid repository name is used"""

    pass


class InvalidRepositoryPath(Error):
    """Raised when an invalid repository path is used"""

    def __init__(self, path: str) -> None:
        """Constructor"""
        super(InvalidRepositoryPath, self).__init__(
            "Invalid repository path: %r" % path
        )


class InvalidRef(Error):
    """Raised by Repository.resolveRef() for invalid refs"""

    def __init__(self, ref: str) -> None:
        """Constructor"""
        super(InvalidRef, self).__init__("Invalid ref: %r" % ref)
        self.ref = ref


class GitCommandError(Error):
    """Raised by Repository methods when 'git' fails unexpectedly"""

    def __init__(
        self,
        argv: Sequence[str],
        returncode: int,
        stdout: Optional[bytes],
        stderr: Optional[bytes],
    ) -> None:
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


Ref = Union[api.commit.Commit, str]
Refs = Union[Ref, Iterable[Ref]]


class Decode(Protocol):
    def commitMetadata(self, value: bytes) -> str:
        ...

    def getCommitMetadataEncodings(self) -> Sequence[str]:
        ...

    def fileContent(self, path: str) -> Callable[[bytes], str]:
        ...

    def getFileContentEncodings(self, path: str) -> Sequence[str]:
        ...

    def path(self, value: bytes) -> str:
        ...

    def getPathEncodings(self) -> Sequence[str]:
        ...


class Repository(api.APIObjectWithId):
    """Representation of one of Critic's repositories"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The repository's unique id"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The repository's short name"""
        ...

    @property
    @abstractmethod
    def path(self) -> str:
        """The repository's (relative) file-system path

        The path is relative the directory in which all repositories are
        stored on the host where Critic's services run. In most cases, the
        absolute file-system path is not relevant."""
        ...

    @property
    @abstractmethod
    async def is_ready(self) -> bool:
        """True if the repository is ready for use

        This returns False temporarily after a repository has been added to
        the database, until it has also been created on disk."""
        ...

    @property
    @abstractmethod
    async def documentation_path(self) -> Optional[str]:
        """Path of the repository's documentation entry point"""
        ...

    @property
    @abstractmethod
    async def urls(self) -> Sequence[str]:
        """The repository's URLs

        The URL types included depends on the effective user's
        'repository.urlType' preference setting."""
        ...

    @property
    @abstractmethod
    def low_level(self) -> gitaccess.GitRepository:
        """Low-level interface for accessing the Git repository

        The interface is returned as a gitaccess.GitRepository object. This
        interface should typically not be used directly."""
        ...

    @abstractmethod
    def withSystemUserDetails(
        self, *, author: bool = True, committer: bool = True
    ) -> ContextManager[gitaccess.GitRepository]:
        ...

    class Head(Protocol):
        @property
        async def value(self) -> Optional[str]:
            """The string value of the repository's HEAD reference"""
            ...

        @property
        async def commit(self) -> Optional[api.commit.Commit]:
            """The commit referenced by the repository's HEAD, or None

            The commit is returned as an api.commit.Commit object. None is
            returned if the repository's HEAD does not reference a commit
            (e.g. if it references a non-existing branch.)"""
            ...

        @property
        async def branch(self) -> Optional[api.branch.Branch]:
            """The branch referenced by the repository's HEAD, or None

            The branch is returned as an api.branch.Branch object. None is
            returned if the repository's HEAD does not reference a branch, or
            if the referenced branch does not exist."""
            ...

    @property
    @abstractmethod
    def head(self) -> Repository.Head:
        ...

    @overload
    @abstractmethod
    async def resolveRef(
        self, ref: str, *, expect: Optional[ObjectType] = None
    ) -> SHA1:
        ...

    @overload
    @abstractmethod
    async def resolveRef(
        self, ref: str, *, expect: Optional[ObjectType] = None, short: Literal[True]
    ) -> str:
        ...

    @abstractmethod
    async def resolveRef(
        self, ref: str, *, expect: Optional[ObjectType] = None, short: bool = False
    ) -> Union[SHA1, str]:
        """Resolve the given ref to a SHA-1 using 'git rev-parse'

        If 'expect' is not None, it should be a string containing a Git
        object type, such as "commit", "tag", "tree" or "blob".  When given,
        it is passed on to 'git rev-parse' using the "<ref>^{<expect>}"
        syntax.

        If 'short' is True, 'git rev-parse' is given the '--short' argument,
        which causes it to return a shortened SHA-1.  If 'short' is an int,
        it is given as the argument value: '--short=N'.

        If the ref can't be resolved, an InvalidRef exception is raised."""
        ...

    @abstractmethod
    async def listRefs(self, *, pattern: Optional[str] = None) -> Collection[str]:
        """List refs using 'git for-each-ref'

        By default, '--format=%(refname)' is used, and the return value is a
        set of the refs output.

        If 'pattern' is not None, it's given to 'git for-each-ref' as the
        last argument, to search for refs whose names match the pattern."""
        ...

    @abstractmethod
    async def listCommits(
        self,
        *,
        include: Optional[Refs] = None,
        exclude: Optional[Refs] = None,
        paths: Optional[Iterable[str]] = None,
        min_parents: Optional[int] = None,
        max_parents: Optional[int] = None,
    ) -> Sequence[api.commit.Commit]:
        """List commits using 'git rev-list'

        Call 'git rev-list' to list commits reachable from the commits in
        'include' but not reachable from the commits in 'exclude'.

        The return value is a list of api.commit.Commit objects."""
        ...

    @abstractmethod
    async def mergeBase(self, *commits: api.commit.Commit) -> api.commit.Commit:
        """Calculate merge-base of two or more commits

        If a single commit argument is specified, it must be a merge commit,
        and the merge-base of all of its parents is returned.

        The return value is an api.commit.Commit object."""
        ...

    @abstractmethod
    async def protectCommit(self, commit: api.commit.Commit) -> None:
        """Create a "hidden" ref to |commit|

        This is done to prevent it from being pruned from the repository by
        the next `git gc` run.

        The ref is created under refs/keepalive/, and is thus not fetched by
        a typically configured repository clone."""
        ...

    @overload
    @abstractmethod
    async def getFileContents(
        self, *, commit: api.commit.Commit, file: api.file.File
    ) -> Optional[bytes]:
        ...

    @overload
    @abstractmethod
    async def getFileContents(self, *, sha1: SHA1) -> Optional[bytes]:
        ...

    @abstractmethod
    async def getFileContents(
        self,
        *,
        commit: Optional[api.commit.Commit] = None,
        file: Optional[api.file.File] = None,
        sha1: Optional[SHA1] = None,
    ) -> Optional[bytes]:
        ...

    class Statistics(Protocol):
        @property
        @abstractmethod
        def commits(self) -> int:
            """Approximate number of commits in the repository

            Specifically, this is the number of commits associated with
            "unmerged" non-review branches in the repository."""
            ...

        @property
        @abstractmethod
        def branches(self) -> int:
            """The number of non-review branches in the repository"""
            ...

        @property
        @abstractmethod
        def reviews(self) -> int:
            """The total number of reviews in the repository

            This includes open and closed reviews, but not draft or dropped
            ones."""
            ...

    @property
    @abstractmethod
    async def statistics(self) -> Statistics:
        """Return some statistics about the repository

        The statistics are returned as a Statistics object."""
        ...

    @abstractmethod
    async def getSetting(self, name: str, default: T) -> T:
        ...

    @abstractmethod
    async def getDecode(
        self, commit: Optional[Union[SHA1, api.commit.Commit]] = None
    ) -> Decode:
        ...


@overload
async def fetch(critic: api.critic.Critic, repository_id: int, /) -> Repository:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, name: str) -> Repository:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, path: str) -> Repository:
    ...


async def fetch(
    critic: api.critic.Critic,
    repository_id: Optional[int] = None,
    /,
    *,
    name: Optional[str] = None,
    path: Optional[str] = None,
) -> Repository:
    """Fetch a Repository object with the given id, name or path"""
    return await fetchImpl.get()(critic, repository_id, name, path)


async def fetchAll(critic: api.critic.Critic) -> Sequence[Repository]:
    """Fetch Repository objects for all repositories

    The return value is a list ordered by the repositories' names."""
    return await fetchAllImpl.get()(critic)


async def fetchHighlighted(
    critic: api.critic.Critic, user: api.user.User
) -> Sequence[Repository]:
    """Fetch Repository objects for repositories that are extra relevant

    The return value is a list ordered by the repositories' names."""
    return await fetchHighlightedImpl.get()(critic, user)


def validateName(name: str) -> str:
    """Validate a (potential) repository name

    If the name is valid, it is returned unchanged. Otherwise an Error
    exception is raised, whose message describe how the name is invalid.

    Note that it is not considered an error that the name names a current
    repository in the system, or that it doesn't."""
    return validateNameImpl.get()(name)


def validatePath(path: str) -> str:
    """Validate a (potential) repository path

    The path should be a relative path.

    If the path is valid, it is returned unchanged. Otherwise an Error
    exception is raised, whose message describe how the path is invalid."""
    return validatePathImpl.get()(path)


resource_name = table_name = "repositories"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[int], Optional[str], Optional[str]],
        Awaitable[Repository],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[[api.critic.Critic], Awaitable[Sequence[Repository]]]
] = FunctionRef()
fetchHighlightedImpl: FunctionRef[
    Callable[[api.critic.Critic, api.user.User], Awaitable[Sequence[Repository]]]
] = FunctionRef()
validateNameImpl: FunctionRef[Callable[[str], str]] = FunctionRef()
validatePathImpl: FunctionRef[Callable[[str], str]] = FunctionRef()
