from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from critic.gitaccess import SHA1


class SyntaxHighlighFile:
    @dataclass
    class Request:
        repository_id: int
        repository_path: str
        sha1: SHA1
        language_id: int
        language_label: str
        conflicts: bool

    @dataclass
    class Response:
        file_id: int


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
