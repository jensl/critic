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
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from ..exceptions import ResultDelayed, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import numeric_id
from ..valuewrapper import ValueWrapper, plain

Part = Union[
    str, Tuple[str, Optional[api.filediff.PartType], Optional[api.filediff.PartState]]
]
Parts = Sequence[Part]
ReadableLine = TypedDict(
    "ReadableLine",
    {
        "type": str,
        "old_offset": int,
        "new_offset": int,
        "content": Parts,
    },
)
ReadableChunk = TypedDict(
    "ReadableChunk",
    {
        "content": Sequence[ReadableLine],
        "old_offset": int,
        "old_count": int,
        "new_offset": int,
        "new_count": int,
    },
)
CompactLine = Tuple[api.filediff.LineType, Parts]
CompactChunk = Tuple[Sequence[CompactLine], int, int, int, int]
Chunk = Union[ReadableChunk, CompactChunk]


def reduce_part(part: api.filediff.Part) -> Part:
    if not part.type and not part.state:
        return part.content
    return (part.content, part.type, part.state)


def reduce_parts(parts: Iterable[api.filediff.Part]) -> Parts:
    return [reduce_part(part) for part in parts]


def reduce_line_readable(line: api.filediff.Line) -> ReadableLine:
    return {
        "type": line.type_string,
        "old_offset": line.old_offset + 1,
        "new_offset": line.new_offset + 1,
        "content": reduce_parts(line.content),
    }


def reduce_chunk_readable(chunk: api.filediff.MacroChunk) -> ReadableChunk:
    return {
        "content": [reduce_line_readable(line) for line in chunk.lines],
        "old_offset": chunk.old_offset + 1,
        "old_count": chunk.old_count,
        "new_offset": chunk.new_offset + 1,
        "new_count": chunk.new_count,
    }


def reduce_line_compact(line: api.filediff.Line) -> CompactLine:
    return (line.type, reduce_parts(line.content))


def reduce_chunk_compact(chunk: api.filediff.MacroChunk) -> CompactChunk:
    return (
        [reduce_line_compact(line) for line in chunk.lines],
        chunk.lines[0].old_offset + 1,
        chunk.lines[0].new_offset + 1,
        chunk.old_count,
        chunk.new_count,
    )


def select_reduce_chunk(
    parameters: Parameters,
) -> Callable[[api.filediff.MacroChunk], Chunk]:
    compact = parameters.query.get("compact", choices=("yes", "no"))
    if compact == "yes":
        return reduce_chunk_compact
    return reduce_chunk_readable


class Filediffs(
    ResourceClass[api.filediff.Filediff],
    api_module=api.filediff,
    exceptions=(api.filediff.Error, api.filechange.Error),
):
    """Source code for a filechange"""

    contexts = (None, "changesets")

    @staticmethod
    async def json(parameters: Parameters, value: api.filediff.Filediff) -> JSONResult:
        """TODO: add documentation"""

        reduce_chunk = select_reduce_chunk(parameters)

        # TODO: load this from the user's config (or make it mandatory and let
        # the client handle config loading).
        context_lines_default = 3
        context_lines = parameters.query.get(
            "context_lines", str(context_lines_default), converter=int
        )
        if context_lines < 0:
            raise UsageError.invalidParameter(
                "context_lines",
                message="Negative number of context lines not supported",
            )

        # TODO: load this from the user's config (or make it mandatory and let
        # the client handle config loading).
        minimum_gap_default = 3
        minimum_gap = parameters.query.get(
            "minimum_gap", str(minimum_gap_default), converter=int
        )
        if minimum_gap <= 0:
            raise UsageError.invalidParameter(
                "minimum_gap", message="Minimum gap must be non-zero and positive"
            )

        async def macro_chunks() -> Optional[ValueWrapper[Sequence[Chunk]]]:
            comments: Optional[Sequence[api.comment.Comment]]
            comment = await parameters.deduce(api.comment.Comment)
            if comment is not None:
                comments = [comment]
            else:
                review = await parameters.deduce(api.review.Review)
                if review is not None:
                    comments = await api.comment.fetchAll(
                        parameters.critic,
                        review=review,
                        changeset=value.filechange.changeset,
                    )
                else:
                    comments = None
            chunks = await value.getMacroChunks(
                context_lines, minimum_gap=minimum_gap, comments=comments
            )
            if chunks is None:
                return None
            return plain(
                cast(Sequence[Chunk], [reduce_chunk(chunk) for chunk in chunks])
            )

        return {
            "file": value.filechange,
            "changeset": value.filechange.changeset,
            "old_is_binary": value.old_is_binary,
            "old_syntax": value.old_syntax,
            "old_length": value.old_length,
            "old_linebreak": value.old_linebreak,
            "delete_count": value.delete_count,
            "new_is_binary": value.new_is_binary,
            "new_syntax": value.new_syntax,
            "new_length": value.new_length,
            "new_linebreak": value.new_linebreak,
            "insert_count": value.insert_count,
            "macro_chunks": macro_chunks(),
        }

    @classmethod
    async def many(
        cls, parameters: Parameters, arguments: Sequence[str]
    ) -> Sequence[api.filediff.Filediff]:
        """TODO: add documentation"""

        changeset = await parameters.deduce(api.changeset.Changeset)
        if changeset is None:
            raise UsageError("changeset needs to be specified, ex. &changeset=<id>")

        if not await changeset.ensure_completion_level(block=False):
            raise ResultDelayed("Changeset is not finished")

        file_ids = [numeric_id(argument) for argument in arguments]
        files = await api.file.fetchMany(parameters.critic, file_ids)
        filechanges = await api.filechange.fetchMany(changeset, files)

        filediffs = {
            filediff.filechange.file.id: filediff
            for filediff in await api.filediff.fetchMany(parameters.critic, filechanges)
        }

        return [filediffs[file_id] for file_id in file_ids]

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.filediff.Filediff]:
        """TODO: add documentation"""

        changeset = await parameters.deduce(api.changeset.Changeset)
        if changeset is None:
            raise UsageError("changeset needs to be specified, ex. &changeset=<id>")

        if not await changeset.ensure_completion_level(block=False):
            raise ResultDelayed("Changeset is not finished")

        return sorted(await api.filediff.fetchAll(changeset))

    @staticmethod
    def resource_id(value: api.filediff.Filediff) -> int:
        return value.filechange.file.id

    @staticmethod
    def sort_key(item: Dict[str, Any]) -> Any:
        return (item["changeset"], item["file"])
