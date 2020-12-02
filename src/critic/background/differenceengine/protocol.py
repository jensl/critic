from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


class SyntaxHighlighFile:
    @dataclass
    class Request:
        source: str
        language: str

        def __repr__(self) -> str:
            return (
                "SyntaxHighlightFile.Request("
                f"source=[{len(self.source)} characters], "
                f"language={self.language!r}"
                ")"
            )

    @dataclass
    class Response:
        lines: Sequence[bytes]
        contexts: Sequence[Tuple[int, int, str]]

        def __repr__(self) -> str:
            return (
                "SyntaxHighlightFile.Response("
                f"lines=[{len(self.lines)} lines], "
                f"contexts={self.contexts!r}"
                ")"
            )


class AnalyzeChangedLines:
    @dataclass
    class Request:
        old_lines: Sequence[str]
        new_lines: Sequence[str]

        def __repr__(self) -> str:
            return (
                "AnalyzeChangedLines.Request("
                f"old_lines=[{len(self.old_lines)} lines], "
                f"new_lines=[{len(self.new_lines)} lines]"
                ")"
            )

    @dataclass
    class Response:
        analysis: Optional[str]
