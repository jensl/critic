from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from critic.gitaccess import SHA1


@dataclass
class Source:
    repository_path: str
    encodings: Sequence[str]
    sha1: SHA1


class SyntaxHighlighFile:
    @dataclass
    class Request:
        source: Source
        repository_id: int
        language_id: int
        language_label: str
        conflicts: bool

    @dataclass
    class Response:
        file_id: int


@dataclass
class Block:
    index: int
    old_offset: int
    old_length: int
    new_offset: int
    new_length: int


class AnalyzeChangedLines:
    @dataclass
    class Request:
        changeset_id: int
        file_id: int
        old_source: Source
        new_source: Source
        blocks: Sequence[Block]

    @dataclass
    class Response:
        duration: float
