from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


class SyntaxHighlighFile:
    @dataclass
    class Request:
        source: str
        language: str

    @dataclass
    class Response:
        lines: Sequence[bytes]
        contexts: Sequence[Tuple[int, int, str]]


class AnalyzeChangedLines:
    @dataclass
    class Request:
        old_lines: Sequence[str]
        new_lines: Sequence[str]

    @dataclass
    class Response:
        analysis: str
