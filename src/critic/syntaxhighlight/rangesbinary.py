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

import asyncio
import logging
import msgpack  # type: ignore
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

from .ranges import SyntaxHighlightRanges

from critic import api
from critic import textutils


class SyntaxHighlightRangesBinary(SyntaxHighlightRanges):
    async def fetch(self) -> None:
        if not self.file_versions:
            return

        sha1s_per_language: Dict[str, Set[str]] = defaultdict(set)
        for file_version in self.file_versions:
            if file_version.language:
                sha1s_per_language[file_version.language].add(file_version.sha1)

        async with api.critic.Query[Tuple[str, int]](
            self.critic,
            """SELECT label, id
                 FROM highlightlanguages
                WHERE {label=languages:array}""",
            languages=list(sha1s_per_language.keys()),
        ) as languages_result:
            language_ids = dict(await languages_result.all())

        highlight_file_ids: Dict[Tuple[str, Optional[str]], int] = {}
        for language, sha1s in sha1s_per_language.items():
            if language is None:
                continue
            async with api.critic.Query[Tuple[int, str]](
                self.critic,
                """SELECT id, sha1
                     FROM highlightfiles
                    WHERE {sha1=sha1s:array}
                      AND language={language}
                      AND highlighted""",
                sha1s=list(sha1s),
                language=language_ids[language],
            ) as files_result:
                async for highlight_file_id, sha1 in files_result:
                    highlight_file_ids[(sha1, language)] = highlight_file_id

        for file_version in self.file_versions:
            key = file_version.sha1, file_version.language
            file_version.is_highlighted = key in highlight_file_ids

            if not file_version.line_ranges:
                # Only checking if highlighted.
                continue

            if not file_version.is_highlighted:
                gitobject = await self.repository.fetchone(
                    file_version.sha1, wanted_object_type="blob"
                )
                plain_lines = textutils.decode(gitobject.asBlob().data).split("\n")
                for line_range in file_version.line_ranges:
                    line_range.lines = [
                        [[line]]
                        for line in plain_lines[line_range.begin : line_range.end]
                    ]
                continue

            highlight_file_id = highlight_file_ids[key]
            conditions = []
            kwargs = {}

            for index, line_range in enumerate(file_version.line_ranges):
                if line_range.begin == 0 and line_range.end is None:
                    # All lines. No need to add a condition to select lines.
                    continue
                kwargs[f"begin{index}"] = line_range.begin
                if line_range.end is None:
                    conditions.append(f"line>={{begin{index}}}")
                else:
                    conditions.append(
                        f"(line>={{begin{index}}} AND line<{{end{index}}})"
                    )
                    kwargs[f"end{index}"] = line_range.end

            if not conditions:
                conditions.append("TRUE")

            lines: List[bytes]

            async with self.critic.query(
                f"""SELECT data
                      FROM highlightlines
                     WHERE file={{highlight_file_id}}
                       AND ({" OR ".join(conditions)})
                  ORDER BY line ASC""",
                highlight_file_id=highlight_file_id,
                **kwargs,
            ) as result:
                lines = await result.scalars()  # type: ignore

            assert isinstance(lines, list)

            for line_range in file_version.line_ranges:
                if line_range.end is None:
                    length = len(lines)
                else:
                    length = line_range.end - line_range.begin
                line_range.lines = [
                    msgpack.unpackb(data, use_list=False, raw=False)  # type: ignore
                    for data in lines[:length]
                ]
                assert len(line_range.lines) == length
                del lines[:length]

            await asyncio.sleep(0)

            assert not lines

    async def close(self) -> None:
        pass
