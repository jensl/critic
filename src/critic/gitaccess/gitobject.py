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

import binascii
import io
import stat
from typing import Dict, Type, Literal, TypeVar, Iterable, FrozenSet, cast

from . import GitError, SHA1, as_sha1
from .gitusertime import GitUserTime

from critic import textutils

ObjectType = Literal["blob", "commit", "tag", "tree"]
OBJECT_TYPES: FrozenSet[ObjectType] = frozenset({"blob", "commit", "tag", "tree"})


def asObjectType(value: str) -> ObjectType:
    assert value in OBJECT_TYPES
    return cast(ObjectType, value)


T = TypeVar("T", bound="GitObject")


class GitObject:
    factory_for: Dict[ObjectType, Type[GitObject]] = {}

    def __init_subclass__(cls) -> None:
        if hasattr(cls, "object_type"):
            GitObject.factory_for[getattr(cls, "object_type")] = cls

    def __init__(self, sha1: SHA1, object_type: ObjectType, data: bytes) -> None:
        self.sha1 = sha1

    def __hash__(self) -> int:
        return hash(self.sha1)

    def __str__(self) -> str:
        return self.sha1

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GitObject) and str(self) == str(other)

    @classmethod
    def fromRawObject(cls: Type[T], raw_object: GitRawObject) -> T:
        return cls(raw_object.sha1, raw_object.object_type, raw_object.data)

    def asBlob(self) -> GitBlob:
        assert isinstance(self, GitBlob)
        return self

    def asCommit(self) -> GitCommit:
        assert isinstance(self, GitCommit)
        return self

    def asTag(self) -> GitTag:
        assert isinstance(self, GitTag)
        return self

    def asTree(self) -> GitTree:
        assert isinstance(self, GitTree)
        return self

    @staticmethod
    def fromCommitItems(
        sha1: bytes,
        tree: bytes,
        parents: Iterable[bytes],
        author: bytes,
        committer: bytes,
        message: bytes,
    ) -> GitObject:
        raise Exception("Invalid use")


class GitRawObject(GitObject):
    def __init__(self, sha1: SHA1, object_type: ObjectType, data: bytes):
        super().__init__(sha1, object_type, data)
        self.object_type = object_type
        self.data = data

    @staticmethod
    def fromRawObject(raw_object: GitRawObject) -> GitRawObject:
        return raw_object

    @staticmethod
    def fromCommitItems(
        sha1: bytes,
        tree: bytes,
        parents: Iterable[bytes],
        author: bytes,
        committer: bytes,
        message: bytes,
    ) -> GitRawObject:
        """Reconstruct a raw object from a semi-parsed commit object"""
        data = io.BytesIO()
        for parent in parents:
            data.write(b"parent %s\n" % parent)
        data.write(
            b"tree %s\nauthor %s\ncommitter %s\n\n%s"
            % (tree, author, committer, message)
        )
        return GitRawObject(as_sha1(sha1.decode("ascii")), "commit", data.getvalue())


class GitBlob(GitObject):
    object_type = "blob"

    def __init__(self, sha1: SHA1, object_type: ObjectType, data: bytes):
        super().__init__(sha1, object_type, data)
        self.data = data


class GitCommit(GitObject):
    object_type = "commit"

    def __init__(
        self, sha1: SHA1, object_type: ObjectType = "commit", data: bytes = b""
    ) -> None:
        super().__init__(sha1, object_type, data)

        tree = author = committer = message = None
        parents = []

        if not data:
            return

        data_buffer = io.BytesIO(data)

        while True:
            line = data_buffer.readline().rstrip(b"\n")
            if not line:
                break
            key, _, value = line.partition(b" ")
            if key == b"tree":
                tree = value
            elif key == b"parent":
                parents.append(value)
            elif key == b"author":
                author = value
            elif key == b"committer":
                committer = value
            else:
                raise GitError("Unknown commit header: %r", line)

        message = data_buffer.read()

        if tree is None or author is None or committer is None:
            raise GitError("Invalid commit data: %r", data)

        self.__set(tree, parents, author, committer, message)

    def __set(
        self,
        tree: bytes,
        parents: Iterable[bytes],
        author: bytes,
        committer: bytes,
        message: bytes,
    ) -> GitCommit:
        self.tree = tree.decode("ascii")
        self.parents = [as_sha1(parent.decode("ascii")) for parent in parents]
        self.author = GitUserTime(textutils.decode(author))
        self.committer = GitUserTime(textutils.decode(committer))
        self.message = textutils.decode(message)
        return self

    @staticmethod
    def fromCommitItems(
        sha1: bytes,
        tree: bytes,
        parents: Iterable[bytes],
        author: bytes,
        committer: bytes,
        message: bytes,
    ) -> GitCommit:
        return GitCommit(as_sha1(sha1.decode("ascii"))).__set(
            tree, parents, author, committer, message
        )


class GitTag(GitObject):
    object_type = "tag"

    def __init__(self, sha1: SHA1, object_type: ObjectType, data: bytes):
        super().__init__(sha1, object_type, data)

        data_buffer = io.BytesIO(data)

        while True:
            line = data_buffer.readline().rstrip(b"\n")
            if not line:
                break
            key, _, value = line.partition(b" ")
            if key == b"object":
                self.object = value.decode("ascii")
            elif key == b"type":
                self.type = value.decode("ascii")
            elif key == b"tag":
                self.tag = value.decode("ascii")
            elif key == b"tagger":
                self.tagger = GitUserTime(textutils.decode(value))
            else:
                raise GitError("Unknown tag header: %r", line)

        self.message = textutils.decode(data_buffer.read())


class GitTreeEntry:
    def __init__(
        self,
        mode: int,
        name: str,
        sha1: SHA1,
        *,
        object_type: ObjectType = None,
        size: int = None
    ):
        self.mode = mode
        self.name = name
        self.sha1 = sha1
        self.object_type = object_type
        self.size = size

    def __repr__(self) -> str:
        return "GitTreeEntry(mode=%o, name=%r, sha1=%r, object_type=%r, size=%r)" % (
            self.mode,
            self.name,
            self.sha1,
            self.object_type,
            self.size,
        )

    def isreg(self) -> bool:
        return stat.S_ISREG(self.mode)

    def isdir(self) -> bool:
        return stat.S_ISDIR(self.mode)


class GitTree(GitObject):
    object_type = "tree"

    def __init__(self, sha1: SHA1, object_type: ObjectType, data: bytes):
        super().__init__(sha1, object_type, data)

        self.entries = []
        self.by_name = {}

        offset = 0
        while offset < len(data):
            mode_end = data.index(b" ", offset)
            entry_mode = data[offset:mode_end]
            offset = mode_end + 1

            name_end = data.index(0, offset)
            entry_name = data[offset:name_end]
            offset = name_end + 1

            entry_sha1 = data[offset : offset + 20]
            offset += 20

            entry = GitTreeEntry(
                int(entry_mode, base=8),
                textutils.decode(entry_name),
                as_sha1(entry_sha1.hex()),
            )
            self.entries.append(entry)
            self.by_name[entry.name] = entry
