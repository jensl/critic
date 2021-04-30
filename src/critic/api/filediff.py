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
from abc import abstractmethod

from typing import Awaitable, Literal, Sequence, Iterable, Callable, Protocol, Optional

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="file diff"):
    pass


class Delayed(api.ResultDelayedError):
    pass


class Filediff(api.APIObject):
    """Representation of the source code for a file in a changeset

    A filediff has a list of macro chunks, where each macro chunk represents
    a partition of a file."""

    @abstractmethod
    def __lt__(self, other: object) -> bool:
        ...

    @property
    @abstractmethod
    def filechange(self) -> api.filechange.FileChange:
        ...

    @property
    @abstractmethod
    def old_is_binary(self) -> bool:
        """True if the old version of the file is binary"""
        ...

    @property
    @abstractmethod
    def old_syntax(self) -> Optional[str]:
        """The syntax of the old version of the file

        The syntax is returned as a string label, or None if the file version
        is binary or if no supported syntax could be determined from the
        filename or content."""
        ...

    @property
    @abstractmethod
    def old_length(self) -> int:
        """The number of lines in the old version of the file"""
        ...

    @property
    @abstractmethod
    def old_linebreak(self) -> bool:
        """True if the old version of the file is non-binary and ends with
        linebreak"""
        ...

    @property
    @abstractmethod
    async def delete_count(self) -> int:
        """The number of "deleted" lines in the diff"""
        ...

    @property
    @abstractmethod
    def new_is_binary(self) -> bool:
        """True if the new version of the file is binary"""
        ...

    @property
    @abstractmethod
    def new_syntax(self) -> Optional[str]:
        """The syntax of the new version of the file

        The syntax is returned as a string label, or None if the file version
        is binary or if no supported syntax could be determined from the
        filename or content."""
        ...

    @property
    @abstractmethod
    def new_length(self) -> int:
        """The number of lines in the new version of the file"""
        ...

    @property
    @abstractmethod
    def new_linebreak(self) -> bool:
        """True if the new version of the file is non-binary and ends with
        linebreak"""
        ...

    @property
    @abstractmethod
    async def insert_count(self) -> int:
        """The number of "inserted" lines in the diff"""
        ...

    @property
    @abstractmethod
    async def changed_lines(self) -> Sequence[ChangedLines]:
        ...

    @abstractmethod
    async def getMacroChunks(
        self,
        context_lines: int,
        *,
        minimum_gap: int = 3,
        comments: Optional[Iterable[api.comment.Comment]] = None,
        block_filter: Optional[Callable[[ChangedLines], bool]] = None,
    ) -> Optional[Sequence[MacroChunk]]:
        """Return padded/merged diff hunks suitable for human consumption

        Pad low-level blocks of changed lines with the specified number of
        context lines, and then merge blocks that overlap, are adjacent, or
        have less than |minimum_gap| number of lines between them. ()
        """
        ...


class ChangedLines(Protocol):
    """Representation of a low-level block of changed lines"""

    @property
    def index(self) -> int:
        ...

    @property
    def offset(self) -> int:
        """Offset from beginning of file or end of preceding block

        In other words, the number of unchanged/context lines before this
        block."""
        ...

    @property
    def delete_count(self) -> int:
        """Number of deleted lines

        Deleted lines can also be thought of as modified lines, in the old
        version of the file, or simply lines that no longer exist (exactly
        the same) in the new version of the file.

        For most purposes, |delete_length| should be used instead."""
        ...

    @property
    def delete_length(self) -> int:
        """Length of the block in the old version of the file

        This always at least |delete_count|, but can be more if adjacent
        blocks only separated by trivial non-modified lines were merged."""
        ...

    @property
    def insert_count(self) -> int:
        """Number of inserted lines

        Inserted lines can also be thought of as modified lines, in the new
        version of the file, or simply lines that did not exist (exactly
        the same) in the old version of the file.

        For most purposes, |insert_length| should be used instead."""
        ...

    @property
    def insert_length(self) -> int:
        """Length of the block in the new version of the file

        This always at least |insert_count|, but can be more if adjacent
        blocks only separated by trivial non-modified lines were merged."""
        ...

    @property
    def analysis(self) -> Optional[str]:
        """String containing analysis of changes"""
        ...


class MacroChunk(Protocol):
    """Representation of a partition of the diff in a file

    A macro chunk contains all lines in the range from the first to the last.
    In other words, if a line is between the first and last line of this
    macro chunk, it will be included in this macro chunk.

    A macro chunk also contains old and new offsets and counts, which
    describe where in the file the lines are from, as well as how many are on
    each side. The two sides represents the old and new version of the file,
    where the old version is what the file looked like just before the first
    (earliest) commit of the changeset, and the new version is what the file
    looked like just after the last (latest) commit of the changeset."""

    @property
    def old_offset(self) -> int:
        ...

    @property
    def new_offset(self) -> int:
        ...

    @property
    def old_count(self) -> int:
        ...

    @property
    def new_count(self) -> int:
        ...

    @property
    def lines(self) -> Sequence[Line]:
        ...


LineType = Literal[1, 2, 3, 4, 5, 6, 7]

LINE_TYPE_CONTEXT: LineType = 1
LINE_TYPE_DELETED: LineType = 2
LINE_TYPE_MODIFIED: LineType = 3
LINE_TYPE_REPLACED: LineType = 4
LINE_TYPE_INSERTED: LineType = 5
LINE_TYPE_WHITESPACE: LineType = 6
LINE_TYPE_CONFLICT: LineType = 7

LINE_TYPE_STRINGS = {
    LINE_TYPE_CONTEXT: "CONTEXT",
    LINE_TYPE_DELETED: "DELETED",
    LINE_TYPE_MODIFIED: "MODIFIED",
    LINE_TYPE_REPLACED: "REPLACED",
    LINE_TYPE_INSERTED: "INSERTED",
    LINE_TYPE_WHITESPACE: "WHITESPACE",
    LINE_TYPE_CONFLICT: "CONFLICT",
}


class Line(Protocol):
    """Representation of a line of a file

    A line represents a change from the old version of a file, to the new
    version of a file.

    A line has a type, which is one of the following:
      CONTEXT
      DELETED
      MODIFIED
      REPLACED
      INSERTED
      WHITESPACE
      CONFLICT

    The type of the line describes how the line changed.
    """

    @property
    def type(self) -> LineType:
        ...

    @property
    def type_string(self) -> str:
        ...

    @property
    def old_offset(self) -> int:
        ...

    @property
    def new_offset(self) -> int:
        ...

    @property
    def content(self) -> Sequence[Part]:
        ...


PartType = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

PART_TYPE_NEUTRAL: PartType = 0
PART_TYPE_OPERATOR: PartType = 1
PART_TYPE_IDENTIFIER: PartType = 2
PART_TYPE_KEYWORD: PartType = 3
PART_TYPE_CHARACTER: PartType = 4
PART_TYPE_STRING: PartType = 5
PART_TYPE_COMMENT: PartType = 6
PART_TYPE_INTEGER: PartType = 7
PART_TYPE_FLOAT: PartType = 8
PART_TYPE_PREPROCESSING: PartType = 9


PartState = Literal[-2, -1, 0, 1, 2]

PART_STATE_DELETED: PartState = -2  # Part does not appear in new version.
PART_STATE_OLD: PartState = -1  # Part appears in both versions with different types.
PART_STATE_NEUTRAL: PartState = 0  # Part is unchanged.
PART_STATE_NEW: PartState = 1  # Part appears in both versions with different types.
PART_STATE_INSERTED: PartState = 2  # Part does not appear in old version.


class Part(Protocol):
    """Representation of a part of a line of code

    A part has a type, which describes what kind of content it contains.
    It can also have a state, meaning the part is either something that was
    removed (in the old version of a file), or added (in the new version of
    a file).

    A part also has some content, which is typically a word (ex. for, in, if)
    or an operator (ex. =, !=, [, ])."""

    @property
    def content(self) -> str:
        ...

    @property
    def type(self) -> PartType:
        ...

    @property
    def state(self) -> PartState:
        ...


async def fetch(filechange: api.filechange.FileChange) -> Filediff:
    return await fetchImpl.get()(filechange.critic, filechange)


async def fetchMany(
    critic: api.critic.Critic, filechanges: Iterable[api.filechange.FileChange]
) -> Sequence[Filediff]:
    filechanges = list(filechanges)
    # All FileChange objects must be from the same changeset.
    assert len(set(filechange.changeset.id for filechange in filechanges)) < 2
    return await fetchManyImpl.get()(critic, filechanges)


async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[Filediff]:
    assert isinstance(changeset, api.changeset.Changeset)
    return await fetchAllImpl.get()(changeset)


resource_name = "filediffs"
table_name = "changesetfiledifferences"


fetchImpl: FunctionRef[
    Callable[
        [api.critic.Critic, api.filechange.FileChange],
        Awaitable[Filediff],
    ]
] = FunctionRef()
fetchManyImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Sequence[api.filechange.FileChange],
        ],
        Awaitable[Sequence[Filediff]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[[api.changeset.Changeset], Awaitable[Sequence[Filediff]]]
] = FunctionRef()
