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
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Any,
    NamedTuple,
    Optional,
    Sequence,
    Dict,
    Tuple,
    Iterable,
    Generator,
    List,
    Iterator,
    Callable,
    Set,
    Literal,
    cast,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import filediff as public
from critic.syntaxhighlight.ranges import SyntaxHighlightRanges
from . import apiobject
from .critic import Critic

COUNTS = "FileDiff.counts"
CHANGED_LINES = "FileDiff.changed_lines"


@dataclass(frozen=True)
class ChangedLines:
    __index: int
    __offset: int
    __delete_count: int
    __delete_length: int
    __insert_count: int
    __insert_length: int
    __analysis: Optional[str]

    @property
    def index(self) -> int:
        return self.__index

    @property
    def offset(self) -> int:
        return self.__offset

    @property
    def delete_count(self) -> int:
        return self.__delete_count

    @property
    def delete_length(self) -> int:
        return self.__delete_length

    @property
    def insert_count(self) -> int:
        return self.__insert_count

    @property
    def insert_length(self) -> int:
        return self.__insert_length

    @property
    def analysis(self) -> Optional[str]:
        return self.__analysis


@dataclass(frozen=True)
class MacroChunk:
    __old_offset: int
    __new_offset: int
    __old_count: int
    __new_count: int
    __lines: Sequence[api.filediff.Line]

    @property
    def old_offset(self) -> int:
        return self.__old_offset

    @property
    def new_offset(self) -> int:
        return self.__new_offset

    @property
    def old_count(self) -> int:
        return self.__old_count

    @property
    def new_count(self) -> int:
        return self.__new_count

    @property
    def lines(self) -> Sequence[api.filediff.Line]:
        return self.__lines


@dataclass(frozen=True)
class Line:
    __type: api.filediff.LineType
    __type_string: str
    __old_offset: int
    __new_offset: int
    __content: Sequence[Part]

    @property
    def type(self) -> api.filediff.LineType:
        return self.__type

    @property
    def type_string(self) -> str:
        return self.__type_string

    @property
    def old_offset(self) -> int:
        return self.__old_offset

    @property
    def new_offset(self) -> int:
        return self.__new_offset

    @property
    def content(self) -> Sequence[Part]:
        return self.__content


@dataclass
class Part:
    __content: str
    __type: api.filediff.PartType = api.filediff.PART_TYPE_NEUTRAL
    __state: api.filediff.PartState = api.filediff.PART_STATE_NEUTRAL

    def __len__(self) -> int:
        return len(self.content)

    @property
    def content(self) -> str:
        return self.__content

    @property
    def type(self) -> api.filediff.PartType:
        return self.__type

    @property
    def state(self) -> api.filediff.PartState:
        return self.__state


class Block(NamedTuple):
    old_offset: int
    old_count: int
    new_offset: int
    new_count: int


class Blocks:
    __blocks: List[Block]
    __old_iter: Optional[Iterator[Block]]
    __old_block: Optional[Block]
    __new_iter: Optional[Iterator[Block]]
    __new_block: Optional[Block]

    def __init__(self) -> None:
        self.__blocks = []
        self.__old_iter = None
        self.__old_block = None
        self.__old_previous_end = 0
        self.__old_last_end = 0
        self.__new_iter = None
        self.__new_block = None
        self.__new_previous_end = 0
        self.__new_last_end = 0
        self.__leading_context = 0

    def __repr__(self) -> str:
        return "Blocks(%r)" % self.__blocks

    def __restart_old(self) -> Optional[Block]:
        self.__old_iter = iter(self.__blocks)
        self.__old_block = None
        return self.__next_old()

    def __next_old(self) -> Optional[Block]:
        assert self.__old_iter
        # assert self.__old_block
        b = self.__old_block
        self.__old_previous_end = b.old_offset + b.old_count if b else 0
        try:
            self.__old_block = next(self.__old_iter)
        except StopIteration:
            self.__old_iter = self.__old_block = None
        return self.__old_block

    def __restart_new(self) -> Optional[Block]:
        self.__new_iter = iter(self.__blocks)
        self.__new_block = None
        return self.__next_new()

    def __next_new(self) -> Optional[Block]:
        assert self.__new_iter
        # assert self.__new_block
        b = self.__new_block
        self.__new_previous_end = b.new_offset + b.new_count if b else 0
        try:
            self.__new_block = next(self.__new_iter)
        except StopIteration:
            self.__new_iter = self.__new_block = None
        return self.__new_block

    @property
    def leading_context(self) -> int:
        return self.__leading_context

    def append(self, block: Block, is_context: bool) -> None:
        if not self.__blocks and not is_context:
            assert block.old_offset == block.new_offset
            self.__leading_context = block.old_offset
        self.__blocks.append(block)
        self.__old_last_end = block.old_offset + block.old_count
        self.__new_last_end = block.new_offset + block.new_count
        self.__restart_old()
        self.__restart_new()

    def find_old(self, old_offset: int) -> Optional[Block]:
        if self.__old_last_end <= old_offset:
            return None
        b = self.__old_block
        if not b or old_offset < b.old_offset:
            if self.__old_previous_end <= old_offset:
                return None
            b = self.__restart_old()
        while b:
            if old_offset < b.old_offset:
                break
            if b.old_offset <= old_offset < b.old_offset + b.old_count:
                return b
            b = self.__next_old()
        return None

    def find_new(self, new_offset: int) -> Optional[Block]:
        if self.__new_last_end <= new_offset:
            return None
        b = self.__new_block
        if not b or new_offset < b.new_offset:
            if self.__new_previous_end <= new_offset:
                return None
            b = self.__restart_new()
        while b:
            if new_offset < b.new_offset:
                break
            if b.new_offset <= new_offset < b.new_offset + b.new_count:
                return b
            b = self.__next_new()
        return None


class MappedLines:
    __old_line_mappings: Dict[int, int]
    __new_line_mappings: Dict[int, int]
    __edits: Dict[Tuple[int, int], str]

    def __init__(self) -> None:
        self.__old_line_mappings = {}
        self.__new_line_mappings = {}
        self.__edits = {}
        self.__changed_blocks = Blocks()
        self.__context_blocks = Blocks()

    def add_line_mapping(self, old_offset: int, new_offset: int, edits: str) -> None:
        self.__old_line_mappings[old_offset] = new_offset
        self.__new_line_mappings[new_offset] = old_offset
        self.__edits[(old_offset, new_offset)] = edits

    @overload
    def is_context(self, *, old_offset: int) -> bool:
        ...

    @overload
    def is_context(self, *, new_offset: int) -> bool:
        ...

    def is_context(
        self, *, old_offset: Optional[int] = None, new_offset: Optional[int] = None
    ) -> bool:
        assert (old_offset is None) != (new_offset is None)
        if old_offset is not None:
            block = self.__changed_blocks.find_old(old_offset)
        else:
            assert new_offset is not None
            block = self.__changed_blocks.find_new(new_offset)
        return block is None

    def get_edits(self, old_offset: int, new_offset: int) -> Optional[str]:
        return self.__edits.get((old_offset, new_offset))

    def add_changed_block(
        self, old_offset: int, old_count: int, new_offset: int, new_count: int
    ) -> None:
        self.__changed_blocks.append(
            Block(old_offset, old_count, new_offset, new_count), False
        )

    def add_context_block(self, old_offset: int, new_offset: int, count: int) -> None:
        self.__context_blocks.append(Block(old_offset, count, new_offset, count), True)

    def lookup_old(self, old_offset: int, /) -> Optional[int]:
        if old_offset in self.__old_line_mappings:
            return self.__old_line_mappings[old_offset]
        block = self.__context_blocks.find_old(old_offset)
        if block is not None:
            return block.new_offset + (old_offset - block.old_offset)
        return None

    def lookup_new(self, new_offset: int, /) -> Optional[int]:
        if new_offset in self.__new_line_mappings:
            return self.__new_line_mappings[new_offset]
        block = self.__context_blocks.find_new(new_offset)
        if block is not None:
            return block.old_offset + (new_offset - block.new_offset)
        return None

    def translate_to_old(self, new_offset: int) -> int:
        block = self.__changed_blocks.find_new(new_offset)
        if block is None:
            assert new_offset < self.__changed_blocks.leading_context
            return new_offset
        return block.old_offset + (new_offset - block.new_offset)

    def translate_to_new(self, old_offset: int) -> int:
        block = self.__changed_blocks.find_old(old_offset)
        if block is None:
            assert old_offset < self.__changed_blocks.leading_context
            return old_offset
        return block.new_offset + (old_offset - block.old_offset)


class PartHelper:
    @staticmethod
    def with_content(part: Part, content: str) -> Part:
        return Part(content, part.type, part.state)

    @staticmethod
    def with_state(part: Part, state: api.filediff.PartState) -> Part:
        return Part(part.content, part.type, state)

    @staticmethod
    def copy(part: Part) -> Part:
        return Part(part.content, part.type, part.state)

    @staticmethod
    def make(content: Optional[Iterable[Tuple[Any, ...]]]) -> Generator[Part, Any, Any]:
        return (Part(*values) for values in (content or []))


# class LineX(object):
#     CONTEXT = 1
#     DELETED = 2
#     MODIFIED = 3
#     REPLACED = 4
#     INSERTED = 5
#     WHITESPACE = 6
#     CONFLICT = 7

#     TYPE_STRINGS = {
#         CONTEXT: "CONTEXT",
#         DELETED: "DELETED",
#         MODIFIED: "MODIFIED",
#         REPLACED: "REPLACED",
#         INSERTED: "INSERTED",
#         WHITESPACE: "WHITESPACE",
#         CONFLICT: "CONFLICT",
#     }

#     def __init__(
#         self, line_type, old_offset, old_content, new_offset, new_content, edits
#     ):
#         self.type = line_type
#         self.old_offset = old_offset
#         self.old_content = old_content
#         self.new_offset = new_offset
#         self.new_content = new_content
#         self.edits = edits or None
#         self.__content = None

#     def type_string(self):
#         return self.TYPE_STRINGS[self.type]

#     def wrap(self):
#         return api.filediff.Line(self)


def getLineContent(
    line_type: api.filediff.LineType,
    old_content: Optional[Sequence[Tuple[Any, ...]]],
    new_content: Optional[Sequence[Tuple[Any, ...]]],
    edits: Optional[str],
) -> Sequence[Part]:
    if line_type == api.filediff.LINE_TYPE_CONTEXT:
        return list(PartHelper.make(old_content))
    else:
        old_parts = PartHelper.make(old_content)
        new_parts = PartHelper.make(new_content)
        if edits:
            return perform_detailed_operations(edits, old_parts, new_parts)
        else:
            return perform_basic_operations(line_type, old_parts, new_parts)


class MacroChunkCreator:
    def __init__(
        self,
        old_offset: int,
        old_count: int,
        old_not_context: Set[int],
        new_offset: int,
        new_count: int,
        new_not_context: Set[int],
        mapped_lines: List[Tuple[int, int, str]],
    ):
        self.old_offset = old_offset
        self.old_count = old_count
        self.old_not_context = old_not_context
        self.old_end = old_offset + old_count
        self.new_offset = new_offset
        self.new_count = new_count
        self.new_not_context = new_not_context
        self.new_end = new_offset + new_count
        self.mapped_lines = mapped_lines

        # FIXME: Typing here.
        self.old_range: Optional[Any] = None
        self.new_range: Optional[Any] = None

    # def __eq__(self, other):
    #     return (
    #         self.old_offset == other.old_offset
    #         and self.old_count == other.old_count
    #         and self.new_offset == other.new_offset
    #         and self.new_count == other.new_count
    #         and self.mapped_lines == other.mapped_lines
    #     )

    # def __repr__(self):
    #     return "MacroChunk(%d, %d, %r, %d, %d, %r, %r)" % (
    #         self.old_offset,
    #         self.old_count,
    #         self.old_range,
    #         self.new_offset,
    #         self.new_count,
    #         self.new_range,
    #         self.mapped_lines,
    #     )

    def getLines(self) -> List[api.filediff.Line]:
        old_offset = self.old_offset
        old_count = self.old_count
        new_offset = self.new_offset
        new_count = self.new_count

        def make_line(
            line_type: Optional[api.filediff.LineType] = None,
            /,
            *,
            edits: Optional[str] = None,
        ) -> api.filediff.Line:
            nonlocal old_offset, old_count, new_offset, new_count
            line_old_offset = old_offset
            line_new_offset = new_offset
            if line_type != api.filediff.LINE_TYPE_INSERTED:
                assert self.old_range
                old_content = self.old_range.lines[old_offset - self.old_offset]
                old_offset += 1
                old_count -= 1
            else:
                old_content = None
            if line_type != api.filediff.LINE_TYPE_DELETED:
                assert self.new_range
                new_content = self.new_range.lines[new_offset - self.new_offset]
                new_offset += 1
                new_count -= 1
            else:
                new_content = None
            if line_type is None:
                if old_content == new_content:
                    line_type = api.filediff.LINE_TYPE_CONTEXT
                elif edits:
                    if edits.startswith("ws"):
                        line_type = api.filediff.LINE_TYPE_WHITESPACE
                        edits = edits[2:].lstrip(",")
                    else:
                        line_type = api.filediff.LINE_TYPE_MODIFIED
                else:
                    line_type = api.filediff.LINE_TYPE_REPLACED
            return Line(
                line_type,
                api.filediff.LINE_TYPE_STRINGS[line_type],
                line_old_offset,
                line_new_offset,
                getLineContent(line_type, old_content, new_content, edits),
            )

        def make_lines() -> Generator[api.filediff.Line, Any, Any]:
            map_offset = 0
            map_old_offset = map_new_offset = edits = None

            def update_mapping() -> None:
                nonlocal map_offset, map_old_offset, map_new_offset, edits
                if map_offset < len(self.mapped_lines):
                    map_old_offset, map_new_offset, edits = self.mapped_lines[
                        map_offset
                    ]
                    if old_offset == map_old_offset and new_offset == map_new_offset:
                        map_offset += 1
                else:
                    map_old_offset = map_new_offset = edits = None

            while old_count or new_count:
                update_mapping()

                if not old_count:
                    yield make_line(api.filediff.LINE_TYPE_INSERTED)
                elif not new_count:
                    yield make_line(api.filediff.LINE_TYPE_DELETED)
                else:
                    if (
                        old_offset not in self.old_not_context
                        and new_offset not in self.new_not_context
                    ):
                        # Neither side is marked as not context, i.e., they are
                        # both context.
                        yield make_line(api.filediff.LINE_TYPE_CONTEXT)
                    elif old_offset == map_old_offset:
                        if new_offset == map_new_offset:
                            yield make_line(edits=edits)
                        else:
                            yield make_line(api.filediff.LINE_TYPE_INSERTED)
                    elif new_offset == map_new_offset:
                        yield make_line(api.filediff.LINE_TYPE_DELETED)
                    elif (
                        old_offset in self.old_not_context
                        and new_offset in self.new_not_context
                    ):
                        yield make_line(api.filediff.LINE_TYPE_REPLACED)
                    elif old_offset in self.old_not_context:
                        yield make_line(api.filediff.LINE_TYPE_DELETED)
                    elif new_offset in self.new_not_context:
                        yield make_line(api.filediff.LINE_TYPE_INSERTED)
                    else:
                        yield make_line()

        return list(make_lines())

    def create(self) -> api.filediff.MacroChunk:
        return MacroChunk(
            self.old_offset,
            self.new_offset,
            self.old_count,
            self.new_count,
            self.getLines(),
        )


def expanded_range(begin: int, end: int, context_lines: int, length: int) -> Set[int]:
    return set(
        range(max(0, begin - context_lines), min(length or 0, end + context_lines))
    )


class MacroChunkGenerator:
    __included_old_lines: Set[int]
    __included_new_lines: Set[int]

    def __init__(
        self, old_length: int, new_length: int, context_lines: int, minimum_gap: int
    ):
        self.old_length = old_length
        self.new_length = new_length
        self.context_lines = context_lines
        self.minimum_gap = minimum_gap

        self.__included_old_lines: Set[int] = set()
        self.__included_new_lines: Set[int] = set()
        self.__mapped_lines = MappedLines()

    def set_changes(
        self,
        changes: List[ChangedLines],
        block_filter: Optional[Callable[[api.filediff.ChangedLines], bool]],
    ) -> None:
        old_offset = new_offset = 0

        for changed_lines in changes:
            # Note: Either of these ranges (but never both) could be empty, in
            #       the case of simply deleted or inserted lines. We still add
            #       the empty range, which is then padded with context. This is
            #       necessary to achieve "balanced" ranges on both sides.

            if self.old_length and self.new_length:
                context_lines = changed_lines.offset
                if context_lines:
                    self.__mapped_lines.add_context_block(
                        old_offset, new_offset, context_lines
                    )

            old_offset += changed_lines.offset
            new_offset += changed_lines.offset

            self.__mapped_lines.add_changed_block(
                old_offset,
                changed_lines.delete_length,
                new_offset,
                changed_lines.insert_length,
            )

            if block_filter is None or block_filter(changed_lines):
                self.__included_old_lines.update(
                    expanded_range(
                        old_offset,
                        old_offset + changed_lines.delete_length,
                        self.context_lines,
                        self.old_length,
                    )
                )
                self.__included_new_lines.update(
                    expanded_range(
                        new_offset,
                        new_offset + changed_lines.insert_length,
                        self.context_lines,
                        self.new_length,
                    )
                )

            if changed_lines.analysis:
                for mapping in changed_lines.analysis.split(";"):
                    lines, _, edits = mapping.partition(":")
                    old_line_string, _, new_line_string = lines.partition("=")
                    old_line = old_offset + int(old_line_string)
                    new_line = new_offset + int(new_line_string)
                    self.__mapped_lines.add_line_mapping(old_line, new_line, edits)

            old_offset += changed_lines.delete_length
            new_offset += changed_lines.insert_length

        if self.old_length and self.new_length:
            context_lines = self.old_length - old_offset
            assert self.new_length - new_offset == context_lines

            if context_lines:
                self.__mapped_lines.add_context_block(
                    old_offset, new_offset, context_lines
                )

    def add_extra(self, side: Literal["old", "new"], begin: int, end: int) -> bool:
        if side == "old":
            updated_lines = self.__included_old_lines
            other_lines = self.__included_new_lines
            length = self.old_length
            lookup_other = self.__mapped_lines.lookup_old
        else:
            updated_lines = self.__included_new_lines
            other_lines = self.__included_old_lines
            length = self.new_length
            lookup_other = self.__mapped_lines.lookup_new

        if updated_lines.isdisjoint(range(begin, end)):
            # No overlap between already included lines and the commented lines.
            return False

        added_lines = expanded_range(begin, end, self.context_lines, length)
        added_lines -= updated_lines

        updated_lines.update(added_lines)

        for offset in added_lines:
            other_offset = lookup_other(offset)
            if other_offset is not None:
                other_lines.add(other_offset)

        return True

    def __iter__(self) -> Iterator[MacroChunkCreator]:
        Pair = Tuple[Optional[int], Optional[int]]

        old_lines = sorted(self.__included_old_lines)
        new_lines = sorted(self.__included_new_lines)
        pairs: List[Pair] = []

        old_offset: Optional[int]
        new_offset: Optional[int]

        while old_lines and new_lines:
            old_offset = old_lines[0]
            mapped_new_offset = self.__mapped_lines.lookup_old(old_offset)
            new_offset = new_lines[0]
            mapped_old_offset = self.__mapped_lines.lookup_new(new_offset)

            if mapped_new_offset is None and mapped_old_offset is None:
                # "Replaced" lines. We'll pair them up just to compress things.
                pairs.append((old_offset, new_offset))
                del old_lines[0]
                del new_lines[0]
            elif mapped_new_offset == new_offset:
                assert mapped_old_offset == old_offset
                pairs.append((old_offset, new_offset))
                del old_lines[0]
                del new_lines[0]
            elif mapped_new_offset is None or mapped_new_offset < new_offset:
                pairs.append((old_offset, None))
                del old_lines[0]
            else:
                assert mapped_old_offset is None or mapped_old_offset < old_offset
                pairs.append((None, new_offset))
                del new_lines[0]

        while old_lines:
            pairs.append((old_lines.pop(0), None))
        while new_lines:
            pairs.append((None, new_lines.pop(0)))

        if not pairs:
            return

        def is_adjacent(pair_a: Pair, pair_b: Pair, minimum_gap: int = 1) -> bool:
            start_a, end_a = pair_a
            start_b, end_b = pair_b
            if (
                start_a is not None
                and start_b is not None
                and start_a + minimum_gap >= start_b
            ):
                return True
            if end_a is not None and end_b is not None and end_a + minimum_gap >= end_b:
                return True
            return False

        def calculate_next_pair(pair: Pair) -> Pair:
            old_offset, new_offset = pair
            if old_offset is None:
                assert new_offset is not None
                old_offset = self.__mapped_lines.translate_to_old(new_offset)
            if new_offset is None:
                assert old_offset is not None
                new_offset = self.__mapped_lines.translate_to_new(old_offset)
            return (old_offset + 1, new_offset + 1)

        previous_pair = pairs[0]
        chunks: List[List[Pair]] = [[previous_pair]]

        for next_pair in pairs[1:]:
            if is_adjacent(previous_pair, next_pair):
                chunks[-1].append(next_pair)
            elif self.minimum_gap > 1 and is_adjacent(
                previous_pair, next_pair, self.minimum_gap
            ):
                gap_pair = calculate_next_pair(previous_pair)
                while not is_adjacent(gap_pair, next_pair):
                    chunks[-1].append(gap_pair)
                    gap_pair = calculate_next_pair(gap_pair)
                chunks[-1].append(next_pair)
            else:
                chunks.append([next_pair])
            previous_pair = next_pair

        for chunk in chunks:
            old_count = new_count = 0
            old_not_context = set()
            new_not_context = set()
            mapped_lines: List[Tuple[int, int, str]] = []
            for old_offset, new_offset in chunk:
                if old_offset is not None:
                    old_count += 1
                    if not self.__mapped_lines.is_context(old_offset=old_offset):
                        old_not_context.add(old_offset)
                if new_offset is not None:
                    new_count += 1
                    if not self.__mapped_lines.is_context(new_offset=new_offset):
                        new_not_context.add(new_offset)
                if old_offset is not None and new_offset is not None:
                    edits = self.__mapped_lines.get_edits(old_offset, new_offset)
                    if edits is not None:
                        mapped_lines.append((old_offset, new_offset, edits))
            old_offset, new_offset = chunk[0]
            if old_offset is None:
                assert new_offset is not None
                old_offset = self.__mapped_lines.translate_to_old(new_offset)
            elif new_offset is None:
                new_offset = self.__mapped_lines.translate_to_new(old_offset)
            yield MacroChunkCreator(
                old_offset,
                old_count,
                old_not_context,
                new_offset,
                new_count,
                new_not_context,
                mapped_lines,
            )


WrapperType = api.filediff.Filediff
ArgumentsType = Tuple[
    api.filechange.FileChange,
    bool,
    int,
    bool,
    Optional[str],
    bool,
    int,
    bool,
    Optional[str],
]
CacheKeyType = Tuple[int, int]


class Filediff(apiobject.APIObject[WrapperType, ArgumentsType, CacheKeyType]):
    wrapper_class = api.filediff.Filediff

    __counts: Optional[Tuple[int, int]]
    __changed_lines: Optional[List[ChangedLines]]
    __macro_chunks: Optional[List[api.filediff.MacroChunk]]

    def __init__(self, args: ArgumentsType):
        (
            self.filechange,
            self.old_is_binary,
            self.old_length,
            self.old_linebreak,
            self.old_syntax,
            self.new_is_binary,
            self.new_length,
            self.new_linebreak,
            self.new_syntax,
        ) = args

        if (
            self.old_is_binary is None
            and self.filechange.old_sha1 is not None
            or self.new_is_binary is None
            and self.filechange.new_sha1 is not None
        ):
            # This indicates that the "content difference" for the file is not
            # yet available in the database.
            raise api.filediff.Delayed("not examined")

        self.__counts = None
        self.__changed_lines = None
        self.__macro_chunks = None

    @staticmethod
    def cacheKey(wrapper: WrapperType) -> CacheKeyType:
        return (wrapper.filechange.changeset.id, wrapper.filechange.file.id)

    @classmethod
    def makeCacheKey(cls, args: ArgumentsType) -> CacheKeyType:
        filechange = args[0]
        return (filechange.changeset.id, filechange.file.id)

    @staticmethod
    def fetchCacheKey(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[api.critic.Critic, Optional[CacheKeyType]]:
        filechange = cast(api.filechange.FileChange, args[0])
        return filechange.critic, (filechange.changeset.id, filechange.file.id)

    @staticmethod
    def fetchManyCacheKeys(
        critic: api.critic.Critic, *args: Any
    ) -> Tuple[api.critic.Critic, List[CacheKeyType], Iterable[Any]]:
        filechanges = cast(Sequence[api.filechange.FileChange], args[0])
        return (
            critic,
            [
                (filechange.changeset.id, filechange.file.id)
                for filechange in filechanges
            ],
            filechanges,
        )

    @staticmethod
    async def __populateCounts(critic: api.critic.Critic) -> None:
        cached_objects = dict(Filediff.allCached(critic))

        cached_by_changeset: Dict[int, List[int]] = {}
        for (changeset_id, file_id), filediff in cached_objects.items():
            if Filediff.fromWrapper(filediff).__counts is None:
                cached_by_changeset.setdefault(changeset_id, []).append(file_id)

        for changeset_id, file_ids in cached_by_changeset.items():
            remaining_file_ids = set(file_ids)

            async with api.critic.Query[Tuple[int, int, int]](
                critic,
                """SELECT file, SUM(delete_count), SUM(insert_count)
                     FROM changesetchangedlines
                    WHERE changeset={changeset_id}
                      AND {file=file_ids:array}
                 GROUP BY file""",
                changeset_id=changeset_id,
                file_ids=file_ids,
            ) as result:
                async for file_id, delete_count, insert_count in result:
                    Filediff.fromWrapper(
                        cached_objects[(changeset_id, file_id)]
                    ).__counts = (
                        delete_count,
                        insert_count,
                    )
                    remaining_file_ids.remove(file_id)

            for file_id in remaining_file_ids:
                Filediff.fromWrapper(
                    cached_objects[(changeset_id, file_id)]
                ).__counts = (0, 0)

    async def getOldCount(self, critic: api.critic.Critic) -> int:
        async with Critic.fromWrapper(critic).criticalSection(COUNTS):
            if self.__counts is None:
                await self.__populateCounts(critic)
                assert self.__counts is not None
        return self.__counts[0]

    async def getNewCount(self, critic: api.critic.Critic) -> int:
        async with Critic.fromWrapper(critic).criticalSection(COUNTS):
            if self.__counts is None:
                await self.__populateCounts(critic)
                assert self.__counts is not None
        return self.__counts[1]

    @staticmethod
    async def __populateChangedLines(critic: api.critic.Critic) -> None:
        cached_objects = dict(Filediff.allCached(critic))

        cached_by_changeset: Dict[int, List[int]] = defaultdict(list)
        need_fetch = []
        for (changeset_id, file_id), filediff in cached_objects.items():
            if Filediff.fromWrapper(filediff).__changed_lines is None:
                cached_by_changeset[changeset_id].append(file_id)
                need_fetch.append((changeset_id, file_id))

        changed_lines: Dict[Tuple[int, int], List[ChangedLines]] = defaultdict(list)

        for changeset_id, file_ids in cached_by_changeset.items():
            async with api.critic.Query[
                Tuple[int, int, int, int, int, int, int, Optional[str]]
            ](
                critic,
                """SELECT file, "index", "offset", delete_count,
                          delete_length, insert_count, insert_length,
                          analysis
                     FROM changesetchangedlines
                    WHERE changeset={changeset_id}
                      AND {file=file_ids:array}
                 ORDER BY file, "index" """,
                changeset_id=changeset_id,
                file_ids=file_ids,
            ) as result:
                async for (
                    file_id,
                    index,
                    offset,
                    delete_count,
                    delete_length,
                    insert_count,
                    insert_length,
                    analysis,
                ) in result:
                    changed_lines[(changeset_id, file_id)].append(
                        ChangedLines(
                            index,
                            offset,
                            delete_count,
                            delete_length,
                            insert_count,
                            insert_length,
                            analysis,
                        )
                    )

        for key in need_fetch:
            Filediff.fromWrapper(cached_objects[key]).__changed_lines = changed_lines[
                key
            ]

    async def getChangedLines(self, critic: api.critic.Critic) -> List[ChangedLines]:
        async with Critic.fromWrapper(critic).criticalSection(CHANGED_LINES):
            if self.__changed_lines is None:
                await self.__populateChangedLines(critic)
                assert self.__changed_lines is not None
        return self.__changed_lines

    async def getMacroChunks(
        self,
        critic: api.critic.Critic,
        context_lines: int,
        minimum_gap: int,
        comments: Optional[Iterable[api.comment.Comment]],
        block_filter: Optional[Callable[[api.filediff.ChangedLines], bool]],
    ) -> Optional[Sequence[api.filediff.MacroChunk]]:
        logger.error("getMacroChunks: path=%s", self.filechange.file.path)
        if not self.__macro_chunks:
            changeset = self.filechange.changeset

            async with Critic.fromWrapper(critic).criticalSection(CHANGED_LINES):
                if self.__changed_lines is None:
                    await self.__populateChangedLines(critic)
                    assert self.__changed_lines is not None

            macro_chunk_generator = MacroChunkGenerator(
                self.old_length, self.new_length, context_lines, minimum_gap
            )

            if self.__changed_lines:
                macro_chunk_generator.set_changes(self.__changed_lines, block_filter)
            elif self.old_length is None or self.new_length is None:
                return None
            else:
                macro_chunk_generator.set_changes(
                    [
                        # ChangedLines(0, 0, self.old_length, self.old_length,
                        #              self.new_length, self.new_length, "")
                    ],
                    block_filter,
                )

            comments_to_add = []

            for comment in comments or []:
                location = await comment.location

                if not isinstance(location, api.comment.FileVersionLocation):
                    continue
                if await location.file != self.filechange.file:
                    continue

                location = await location.translateTo(changeset=changeset)

                if not location:
                    continue

                comments_to_add.append((comment, location))

            # Add comments repeatedly until there are no more comments to add or
            # none of the remaining comments were added. We only add comments
            # that touch lines that are already included in the diff, but when
            # we add one comment, the set of included lines expand, which may
            # lead to another comment's touched lines become included.

            while comments_to_add:
                retry_comments = []
                was_updated = False

                for comment, location in comments_to_add:
                    if macro_chunk_generator.add_extra(
                        location.side, location.first_line - 1, location.last_line
                    ):
                        was_updated = True
                    else:
                        retry_comments.append((comment, location))

                if not was_updated:
                    break

                comments_to_add = retry_comments

            macro_chunks = []
            for macro_chunk in macro_chunk_generator:
                macro_chunks.append(macro_chunk)
                await asyncio.sleep(0)

            repository = await changeset.repository

            async with SyntaxHighlightRanges.make(repository) as ranges:
                old_version = new_version = None

                if self.filechange.old_sha1:
                    old_version = ranges.add_file_version(
                        self.filechange.old_sha1, self.old_syntax, changeset.is_replay
                    )
                if self.filechange.new_sha1:
                    new_version = ranges.add_file_version(
                        self.filechange.new_sha1, self.new_syntax, False
                    )

                for macro_chunk in macro_chunks:
                    if old_version and macro_chunk.old_count:
                        macro_chunk.old_range = old_version.add_line_range(
                            macro_chunk.old_offset, macro_chunk.old_end
                        )
                    if new_version and macro_chunk.new_count:
                        macro_chunk.new_range = new_version.add_line_range(
                            macro_chunk.new_offset, macro_chunk.new_end
                        )

                await ranges.fetch()

            self.__macro_chunks = [macro_chunk.create() for macro_chunk in macro_chunks]

        return self.__macro_chunks


# Note: All FileChange objects are automatically valid "ids". If one doesn't
#       resolve to the expected database rows, it means the content difference
#       hasn't been completely processed yet, so a different exception should be
#       raised.
class IncompleteChangeset(api.filediff.Delayed):
    def __init__(self) -> None:
        super().__init__("incomplete changeset")


@public.fetchImpl
@Filediff.cached
async def fetch(
    critic: api.critic.Critic, filechange: api.filechange.FileChange
) -> WrapperType:
    if not await filechange.changeset.ensure("changedlines", block=False):
        raise api.filediff.Delayed("not finished")

    async with api.critic.Query[
        Tuple[bool, int, bool, Optional[str], bool, int, bool, Optional[str]]
    ](
        critic,
        """SELECT csfd.old_is_binary, csfd.old_length, csfd.old_linebreak,
                  old_hll.label,
                  csfd.new_is_binary, csfd.new_length, csfd.new_linebreak,
                  new_hll.label
             FROM changesetfiles AS csf
             JOIN changesetfiledifferences AS csfd ON (
                    csfd.changeset=csf.changeset AND
                    csfd.file=csf.file
                  )
  LEFT OUTER JOIN highlightfiles AS old_hlf ON (
                    old_hlf.id=csfd.old_highlightfile
                  )
  LEFT OUTER JOIN highlightlanguages AS old_hll ON (
                    old_hll.id=old_hlf.language)
  LEFT OUTER JOIN highlightfiles AS new_hlf ON (
                    new_hlf.id=csfd.new_highlightfile
                  )
  LEFT OUTER JOIN highlightlanguages AS new_hll ON (
                    new_hll.id=new_hlf.language)
            WHERE csf.changeset={changeset}
              AND csf.file={file}""",
        changeset=filechange.changeset,
        file=filechange.file,
    ) as result:
        try:
            return await Filediff.makeOne(
                critic, values=(filechange, *await result.one())
            )
        except result.ZeroRowsInResult:
            raise IncompleteChangeset()


@public.fetchManyImpl
@Filediff.cachedMany
async def fetchMany(
    critic: api.critic.Critic, filechanges: Sequence[api.filechange.FileChange]
) -> Sequence[WrapperType]:
    # APIObject.cachedMany should short-cut empty requests.
    assert filechanges

    # All FileChange objects are guaranteed to be from the same Changeset,
    # either by api.filediff.fetchMany() or because we're called from fetchAll()
    # which uses `changeset.files` as the argument.
    changeset = filechanges[0].changeset

    if not await changeset.ensure("changedlines", block=False):
        raise api.filediff.Delayed("not finished")

    filechange_by_file_id = {
        filechange.file.id: filechange for filechange in filechanges
    }

    async with api.critic.Query[
        Tuple[int, bool, int, bool, Optional[str], bool, int, bool, Optional[str]]
    ](
        critic,
        """SELECT csf.file,
                  csfd.old_is_binary, csfd.old_length, csfd.old_linebreak,
                  old_hll.label,
                  csfd.new_is_binary, csfd.new_length, csfd.new_linebreak,
                  new_hll.label
             FROM changesetfiles AS csf
             JOIN changesetfiledifferences AS csfd ON (
                    csfd.changeset=csf.changeset AND
                    csfd.file=csf.file
                  )
  LEFT OUTER JOIN highlightfiles AS old_hlf ON (
                    old_hlf.id=csfd.old_highlightfile
                  )
  LEFT OUTER JOIN highlightlanguages AS old_hll ON (
                    old_hll.id=old_hlf.language
                  )
  LEFT OUTER JOIN highlightfiles AS new_hlf ON (
                    new_hlf.id=csfd.new_highlightfile
                  )
  LEFT OUTER JOIN highlightlanguages AS new_hll ON (
                    new_hll.id=new_hlf.language
                  )
            WHERE csf.changeset={changeset}
              AND {csf.file=file_ids:array}""",
        changeset=changeset,
        file_ids=list(filechange_by_file_id.keys()),
    ) as result:
        try:
            return await Filediff.make(
                critic,
                (
                    (
                        filechange_by_file_id[file_id],
                        old_is_binary,
                        old_length,
                        old_linebreak,
                        old_syntax,
                        new_is_binary,
                        new_length,
                        new_linebreak,
                        new_syntax,
                    )
                    async for (
                        file_id,
                        old_is_binary,
                        old_length,
                        old_linebreak,
                        old_syntax,
                        new_is_binary,
                        new_length,
                        new_linebreak,
                        new_syntax,
                    ) in result
                ),
            )
        except result.ZeroRowsInResult:
            raise IncompleteChangeset()


@public.fetchAllImpl
async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[WrapperType]:
    files = await changeset.files
    if files is None:
        raise IncompleteChangeset()
    return await fetchMany(changeset.critic, files)


class Parts:
    def __init__(self, parts: Iterable[Part]):
        self.parts = list(parts)
        self.offset = 0

    def __repr__(self) -> str:
        return f"Parts(offset={self.offset}, parts={self.parts!r})"

    def __len__(self) -> int:
        return sum(len(part.content) for part in self.parts)

    def equals(self, string: str) -> bool:
        value = "".join(part.content for part in self.parts)
        return value == string

    def extract(self, length: int) -> Generator[Part, Any, Any]:
        self.offset += length
        while self.parts and len(self.parts[0].content) <= length:
            part = self.parts.pop(0)
            length -= len(part.content)
            yield part
        if length:
            part = self.parts[0]
            head_part = PartHelper.with_content(part, part.content[:length])
            self.parts[0] = PartHelper.with_content(part, part.content[length:])
            yield head_part

    def skip(self, length: int) -> None:
        self.offset += length
        while self.parts and len(self.parts[0].content) <= length:
            length -= len(self.parts.pop(0).content)
        if length:
            part = self.parts[0]
            self.parts[0] = PartHelper.with_content(part, part.content[length:])


def extract_context(
    old_parts: Parts, new_parts: Parts, context_length: int
) -> Generator[Part, Any, Any]:
    old_parts_list = list(old_parts.extract(context_length))
    new_parts_list = list(new_parts.extract(context_length))

    if old_parts_list == new_parts_list:
        yield from old_parts_list
        return

    old_parts_iter = iter(old_parts_list)
    new_parts_iter = iter(new_parts_list)

    old_part = next(old_parts_iter, None)
    new_part = next(new_parts_iter, None)
    old_offset = new_offset = 0

    def consume_old_part() -> None:
        nonlocal old_part, old_offset
        part = old_part
        assert part
        old_offset += len(part)
        old_part = next(old_parts_iter, None)

    def emit_old_part() -> Part:
        assert old_part
        part = old_part
        consume_old_part()
        return part

    def consume_new_part() -> None:
        nonlocal new_part, new_offset
        assert new_part
        new_offset += len(new_part)
        new_part = next(new_parts_iter, None)

    def emit_new_part() -> Part:
        assert new_part
        part = new_part
        consume_new_part()
        return part

    while True:
        if old_part is None and new_part is None:
            break

        if old_offset == new_offset and old_part == new_part:
            # Output the old part as "neutral", i.e. unchanged.
            yield emit_old_part()
            # Discard the new part, as it's identical to the old part.
            consume_new_part()
            continue

        if old_offset < new_offset and old_part is not None:
            yield PartHelper.with_state(emit_old_part(), api.filediff.PART_STATE_OLD)
            continue
        if new_offset < old_offset and new_part is not None:
            yield PartHelper.with_state(emit_new_part(), api.filediff.PART_STATE_NEW)
            continue

        if old_part is not None:
            yield PartHelper.with_state(emit_old_part(), api.filediff.PART_STATE_OLD)
        if new_part is not None:
            yield PartHelper.with_state(emit_new_part(), api.filediff.PART_STATE_NEW)


def perform_detailed_operations(
    operations: str, old_content: Iterable[Part], new_content: Iterable[Part]
) -> Sequence[Part]:
    processed_content: List[Part] = []

    old_content = list(old_content)
    new_content = list(new_content)

    old_parts = Parts(old_content)
    new_parts = Parts(new_content)

    old_range: Optional[str]
    new_range: Optional[str]

    for operation in operations.split(","):
        if operation[0] == "r":
            old_range, _, new_range = operation[1:].partition("=")
        elif operation[0] == "d":
            old_range = operation[1:]
            new_range = None
        else:
            old_range = None
            new_range = operation[1:]

        if old_range:
            old_begin, old_end = list(map(int, old_range.split("-")))

            context_length = old_begin - old_parts.offset
            if context_length:
                processed_content.extend(
                    extract_context(old_parts, new_parts, context_length)
                )

            deleted_length = old_end - old_begin
            processed_content.extend(
                PartHelper.with_state(part, api.filediff.PART_STATE_DELETED)
                for part in old_parts.extract(deleted_length)
            )

        if new_range:
            new_begin, new_end = list(map(int, new_range.split("-")))

            if not old_range:
                context_length = new_begin - new_parts.offset
                if context_length:
                    processed_content.extend(
                        extract_context(old_parts, new_parts, context_length)
                    )

            inserted_length = new_end - new_begin
            processed_content.extend(
                PartHelper.with_state(part, api.filediff.PART_STATE_INSERTED)
                for part in new_parts.extract(inserted_length)
            )

    assert len(old_parts) == len(new_parts), repr(
        (operations, old_content, new_content)
    )
    processed_content.extend(extract_context(old_parts, new_parts, len(old_parts)))

    return processed_content


def perform_basic_operations(
    line_type: api.filediff.LineType,
    old_content: Iterable[Part],
    new_content: Iterable[Part],
) -> Sequence[Part]:
    if old_content is not None and new_content is not None:
        return [
            PartHelper.with_state(part, api.filediff.PART_STATE_DELETED)
            for part in old_content
        ] + [
            PartHelper.with_state(part, api.filediff.PART_STATE_INSERTED)
            for part in new_content
        ]
    elif old_content is not None:
        return list(old_content)
    assert new_content
    return list(new_content)
