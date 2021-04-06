from typing import Callable, Iterator, List, Literal, Optional, Set, Tuple

from critic import api
from .macrochunkcreator import MacroChunkCreator
from .mappedlines import MappedLines
from .types import ChangedLines


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
