# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from types import TracebackType
from typing import List, Sequence, Any, Optional, AsyncIterator, Type

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess


class SyntaxHighlightRangesError(Exception):
    pass


class SyntaxHighlightRanges(ABC):
    Error = SyntaxHighlightRangesError

    class LineRange:
        lines: Optional[Sequence[Any]] = None

        def __init__(self, begin: int, end: Optional[int]) -> None:
            self.begin = begin
            self.end = end

        def __repr__(self) -> str:
            return "LineRange(begin=%r, end=%r, lines=%r)" % (
                self.begin,
                self.end,
                self.lines,
            )

        def __len__(self) -> int:
            return len(self.lines) if self.lines else 0

    class FileVersion:
        is_highlighted: Optional[bool] = None

        def __init__(
            self, sha1: gitaccess.SHA1, language: str, conflicts: bool
        ) -> None:
            self.sha1 = sha1
            self.language = language
            self.conflicts = conflicts
            self.line_ranges: List[SyntaxHighlightRanges.LineRange] = []

        def __repr__(self) -> str:
            return "FileVersion(sha1=%r, language=%r, line_ranges=%r)" % (
                self.sha1,
                self.language,
                self.line_ranges,
            )

        def add_line_range(
            self, begin: int = 0, end: int = None
        ) -> SyntaxHighlightRanges.LineRange:
            assert end is None or begin < end, (begin, end)
            line_range = SyntaxHighlightRanges.LineRange(begin, end)
            self.line_ranges.append(line_range)
            return line_range

    def __init__(self, repository: api.repository.Repository):
        self.critic = repository.critic
        self.loop = self.critic.loop
        self.repository = repository.low_level
        self.file_versions: List[SyntaxHighlightRanges.FileVersion] = []

    def __repr__(self):
        return "Ranges(file_versions=%r)" % self.file_versions

    def add_file_version(
        self, sha1: gitaccess.SHA1, language: str, conflicts: bool
    ) -> FileVersion:
        file_version = SyntaxHighlightRanges.FileVersion(sha1, language, conflicts)
        self.file_versions.append(file_version)
        return file_version

    @abstractmethod
    async def fetch(self) -> None:
        """Implemented by sub-class"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Implemented by sub-class"""
        ...

    @staticmethod
    def make(repository: api.repository.Repository):
        return SyntaxHighlightRangesBinary(repository)

    async def __aenter__(self) -> SyntaxHighlightRanges:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        return None


from .rangesbinary import SyntaxHighlightRangesBinary
