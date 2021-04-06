from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from critic import api


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
