from typing import Any, Generator, Iterable

from .parthelper import PartHelper
from .types import Part


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
