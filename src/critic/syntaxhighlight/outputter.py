import msgpack
from typing import Union, Tuple, Optional, List

from critic.api.filediff import PartType, PART_TYPE_NEUTRAL


Part = Union[Tuple[str], Tuple[str, PartType]]


class Outputter:
    line: List[Part]
    previous_type: Optional[PartType]
    result: List[bytes]

    def __init__(self):
        self.line = []
        self.previous_type = None
        self.result = []

    def writeMultiline(self, token_type: PartType, content: str) -> None:
        parts = content.split("\n")
        for part in parts[:-1]:
            if part:
                self._writePart(token_type, part)
            self._endLine()
        if parts[-1]:
            self._writePart(token_type, parts[-1])

    def writeSingleline(self, token_type: PartType, content: str) -> None:
        assert "\n" not in content
        self._writePart(token_type, content)

    def writePlain(self, content: str) -> None:
        parts = content.split("\n")
        for part in parts[:-1]:
            if part:
                self._writePlain(part)
            self._endLine()
        if parts[-1]:
            self._writePlain(parts[-1])

    def flush(self) -> None:
        if self.line:
            self._emitLine(self.line)

    def _writePart(self, token_type: PartType, content: str) -> None:
        if self.previous_type == token_type:
            self.line[-1] = (self.line[-1][0] + content, token_type)
        else:
            self.line.append((content, token_type))
            self.previous_type = token_type

    def _writePlain(self, content: str) -> None:
        if self.previous_type == PART_TYPE_NEUTRAL:
            self.line[-1] = (self.line[-1][0] + content, PART_TYPE_NEUTRAL)
        else:
            self.line.append((content,))
            self.previous_type = PART_TYPE_NEUTRAL

    def _endLine(self) -> None:
        self._emitLine(self.line)
        self.line = []
        self.previous_type = None

    def _emitLine(self, line: List[Part]) -> None:
        self.result.append(msgpack.packb(line, use_bin_type=True))
