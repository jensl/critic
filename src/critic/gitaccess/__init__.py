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

import asyncio
import logging
import re
from dataclasses import dataclass
from distutils.spawn import find_executable
from typing import Literal, Mapping, NewType, Optional, Type, cast

logger = logging.getLogger(__name__)

SHA1 = NewType("SHA1", str)


def is_sha1(value: str) -> bool:
    return bool(SHA1_PATTERN.match(value))


def as_sha1(value: str) -> SHA1:
    if not is_sha1(value):
        raise ValueError(f"invalid SHA-1: {value!r}")
    return cast(SHA1, value)


from .giterror import (
    GitError,
    GitRepositoryError,
    GitProcessError,
    GitReferenceError,
    GitFetchError,
)

from .gitobject import (
    ObjectType,
    GitObject,
    GitRawObject,
    GitBlob,
    GitCommit,
    GitTag,
    GitTreeEntry,
    GitTree,
)

from .gitusertime import GitUserTime

SHA1_PATTERN = re.compile("^[0-9a-fA-F]{40}$")

# This is what an empty tree object hashes to.
EMPTY_TREE_SHA1 = SHA1("4b825dc642cb6eb9a060e54bf8d69288fbee4904")

# This is the file mode of a sub-module ("git link")
GIT_LINK_MODE = 0o160000

GIT_EXECUTABLE: Optional[str] = None


def git() -> str:
    global GIT_EXECUTABLE
    if GIT_EXECUTABLE is None:
        executable = find_executable("git")
        if executable is None:
            raise GitError("No Git executable found!")
        GIT_EXECUTABLE = executable
        logger.debug("using git executable: %s", GIT_EXECUTABLE)
    return GIT_EXECUTABLE


@dataclass
class GitRemoteRefs:
    refs: Mapping[str, SHA1]
    symbolic_refs: Mapping[str, str]


class FetchJob:
    future: "asyncio.Future[GitObject]"

    def __init__(
        self,
        object_id: Optional[SHA1],
        *,
        wanted_object_type: Optional[ObjectType] = None,
        object_factory: Optional[Type[GitObject]] = None,
    ) -> None:
        self.object_id = object_id
        self.wanted_object_type = wanted_object_type
        self.object_factory = object_factory or resolve_object_factory(
            wanted_object_type
        )
        self.future = asyncio.get_running_loop().create_future()


FetchRangeOrder = Literal["date", "topo"]
RevlistFlag = Literal[
    "ancestry-path",
    "cherry-mark",
    "cherry-pick",
    "cherry",
    "first-parent",
    "left-only",
    "merges",
    "no-merges",
    "reverse",
    "right-only",
]
RevlistOrder = Literal["date", "author-date", "topo"]
StreamCommand = Literal["http-backend", "receive-pack", "upload-pack", "upload-archive"]


from .gitrepository import (
    FetchJob,
    GitRepository,
    resolve_object_factory,
)
from .gitrepositoryimpl import GitRepositoryImpl

__all__ = [
    "EMPTY_TREE_SHA1",
    "FetchJob",
    "FetchRangeOrder",
    "GitBlob",
    "GitCommit",
    "GitFetchError",
    "GitObject",
    "GitProcessError",
    "GitRawObject",
    "GitReferenceError",
    "GitRemoteRefs",
    "GitRepository",
    "GitRepositoryError",
    "GitRepositoryImpl",
    "GitTag",
    "GitTree",
    "GitTreeEntry",
    "GitUserTime",
    "RevlistFlag",
    "RevlistOrder",
    "StreamCommand",
    "git",
    "resolve_object_factory",
]
