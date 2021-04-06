from typing import Dict, Optional, Tuple, overload

from .blocks import Block, Blocks


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
