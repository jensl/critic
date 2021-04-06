from typing import Iterator, List, NamedTuple, Optional


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
