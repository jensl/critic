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

import asyncio
from dataclasses import dataclass
import logging
from collections import defaultdict
from typing import (
    Collection,
    Mapping,
    Optional,
    Sequence,
    Dict,
    Tuple,
    Iterable,
    List,
    Callable,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import filediff as public
from critic.api.apiobject import Actual
from critic.syntaxhighlight.ranges import SyntaxHighlightRanges
from ..apiobject import APIObjectImpl
from .macrochunkgenerator import MacroChunkGenerator
from .types import ChangedLines

PublicType = public.Filediff
RowType = Tuple[int, bool, int, bool, Optional[str], bool, int, bool, Optional[str]]


class Filediff(PublicType, APIObjectImpl, module=public):
    wrapper_class = public.Filediff

    __counts: Optional[Tuple[int, int]]
    __changed_lines: Optional[List[ChangedLines]]
    __macro_chunks: Optional[List[public.MacroChunk]]

    def __init__(self, filechange: api.filechange.FileChange, row: RowType):
        super().__init__(filechange.critic)

        self.__filechange = filechange
        (
            file_id,
            self.__old_is_binary,
            self.__old_length,
            self.__old_linebreak,
            self.__old_syntax,
            self.__new_is_binary,
            self.__new_length,
            self.__new_linebreak,
            self.__new_syntax,
        ) = row

        assert file_id == filechange.file.id

        if (
            self.__old_is_binary is None
            and self.__filechange.old_sha1 is not None
            or self.__new_is_binary is None
            and self.__filechange.new_sha1 is not None
        ):
            # This indicates that the "content difference" for the file is not
            # yet available in the database.
            raise public.Delayed("not examined")

        self.__counts = None
        self.__changed_lines = None
        self.__macro_chunks = None

    def __hash__(self) -> int:
        return hash((Filediff, self.filechange))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Filediff) and self.filechange == other.filechange

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Filediff)
        return self.filechange < other.filechange

    def getCacheKeys(self) -> Collection[object]:
        return (self.__filechange,)

    async def refresh(self: Actual) -> Actual:
        return self

    @staticmethod
    async def __populateCounts(critic: api.critic.Critic) -> None:
        cached_objects = cast(
            Mapping[api.filechange.FileChange, Filediff], Filediff.allCached()
        )

        cached_by_changeset: Dict[
            api.changeset.Changeset, Dict[int, api.filechange.FileChange]
        ] = {}
        for filechange, filediff in cached_objects.items():
            if filediff.__counts is None:
                cached_by_changeset.setdefault(filechange.changeset, {})[
                    filechange.file.id
                ] = filechange

        for changeset, filechanges in cached_by_changeset.items():
            async with api.critic.Query[Tuple[int, int, int]](
                critic,
                """SELECT file, SUM(delete_count), SUM(insert_count)
                     FROM changesetchangedlines
                    WHERE changeset={changeset}
                      AND file=ANY({files})
                 GROUP BY file""",
                changeset=changeset,
                files=[*filechanges.keys()],
            ) as result:
                async for file_id, delete_count, insert_count in result:
                    cached_objects[filechanges.pop(file_id)].__counts = (
                        delete_count,
                        insert_count,
                    )

            for filechange in filechanges.values():
                cached_objects[filechange].__counts = (0, 0)

    @property
    def filechange(self) -> api.filechange.FileChange:
        return self.__filechange

    @property
    def old_is_binary(self) -> bool:
        return self.__old_is_binary

    @property
    def old_syntax(self) -> Optional[str]:
        return self.__old_syntax

    @property
    def old_length(self) -> int:
        return self.__old_length

    @property
    def old_linebreak(self) -> bool:
        return self.__old_linebreak

    @property
    async def old_count(self) -> int:
        if self.__counts is None:
            await self.__populateCounts(self.critic)
            assert self.__counts is not None
        return self.__counts[0]

    @property
    def new_is_binary(self) -> bool:
        return self.__new_is_binary

    @property
    def new_syntax(self) -> Optional[str]:
        return self.__new_syntax

    @property
    def new_length(self) -> int:
        return self.__new_length

    @property
    def new_linebreak(self) -> bool:
        return self.__new_linebreak

    @property
    async def new_count(self) -> int:
        if self.__counts is None:
            await self.__populateCounts(self.critic)
            assert self.__counts is not None
        return self.__counts[1]

    @staticmethod
    async def __populateChangedLines(critic: api.critic.Critic) -> None:
        cached_objects = cast(
            Mapping[api.filechange.FileChange, Filediff], Filediff.allCached()
        )

        cached_by_changeset: Dict[
            api.changeset.Changeset, Dict[int, api.filechange.FileChange]
        ] = defaultdict(dict)
        need_fetch = []
        for filechange, filediff in cached_objects.items():
            if filediff.__changed_lines is None:
                cached_by_changeset[filechange.changeset][
                    filechange.file.id
                ] = filechange
                need_fetch.append(filechange)

        changed_lines: Dict[
            api.filechange.FileChange, List[ChangedLines]
        ] = defaultdict(list)

        for changeset, filechanges in cached_by_changeset.items():
            async with api.critic.Query[
                Tuple[int, int, int, int, int, int, int, Optional[str]]
            ](
                critic,
                """SELECT file, "index", "offset", delete_count,
                          delete_length, insert_count, insert_length,
                          analysis
                     FROM changesetchangedlines
                    WHERE changeset={changeset}
                      AND file=ANY({files})
                 ORDER BY file, "index" """,
                changeset=changeset,
                files=[*filechanges.keys()],
            ) as result:
                async for (
                    file_id,
                    index,
                    offset,
                    delete_count,
                    delete_length,
                    insert_count,
                    insert_length,
                    analysis,
                ) in result:
                    changed_lines[filechanges[file_id]].append(
                        ChangedLines(
                            index,
                            offset,
                            delete_count,
                            delete_length,
                            insert_count,
                            insert_length,
                            analysis,
                        )
                    )

        for filechange in need_fetch:
            cached_objects[filechange].__changed_lines = changed_lines[filechange]

    @property
    async def changed_lines(self) -> Sequence[ChangedLines]:
        if self.__changed_lines is None:
            await self.__populateChangedLines(self.critic)
            assert self.__changed_lines is not None
        return self.__changed_lines

    async def getMacroChunks(
        self,
        context_lines: int,
        *,
        minimum_gap: int = 3,
        comments: Optional[Iterable[api.comment.Comment]] = None,
        block_filter: Optional[Callable[[public.ChangedLines], bool]] = None,
    ) -> Optional[Sequence[public.MacroChunk]]:
        if not self.__macro_chunks:
            changeset = self.filechange.changeset

            if self.__changed_lines is None:
                await self.__populateChangedLines(self.critic)
                assert self.__changed_lines is not None

            macro_chunk_generator = MacroChunkGenerator(
                self.old_length, self.new_length, context_lines, minimum_gap
            )

            if self.__changed_lines:
                macro_chunk_generator.set_changes(self.__changed_lines, block_filter)
            elif self.old_length is None or self.new_length is None:
                return None
            else:
                macro_chunk_generator.set_changes(
                    [
                        # ChangedLines(0, 0, self.old_length, self.old_length,
                        #              self.new_length, self.new_length, "")
                    ],
                    block_filter,
                )

            comments_to_add: List[
                Tuple[api.comment.Comment, api.comment.FileVersionLocation]
            ] = []

            if comments:
                for comment in comments:
                    location = await comment.location

                    if not isinstance(location, api.comment.FileVersionLocation):
                        continue
                    if await location.file != self.filechange.file:
                        continue

                    location = await location.translateTo(changeset=changeset)

                    if not location:
                        continue

                    comments_to_add.append((comment, location))

            # Add comments repeatedly until there are no more comments to add or
            # none of the remaining comments were added. We only add comments
            # that touch lines that are already included in the diff, but when
            # we add one comment, the set of included lines expand, which may
            # lead to another comment's touched lines become included.

            while comments_to_add:
                retry_comments = []
                was_updated = False

                for comment, location in comments_to_add:
                    assert location.side
                    if macro_chunk_generator.add_extra(
                        location.side, location.first_line - 1, location.last_line
                    ):
                        was_updated = True
                    else:
                        retry_comments.append((comment, location))

                if not was_updated:
                    break

                comments_to_add = retry_comments

            macro_chunks = []
            for macro_chunk in macro_chunk_generator:
                macro_chunks.append(macro_chunk)
                await asyncio.sleep(0)

            repository = await changeset.repository

            async with SyntaxHighlightRanges.make(repository) as ranges:
                old_version = new_version = None

                if self.filechange.old_sha1:
                    old_version = ranges.add_file_version(
                        self.filechange.old_sha1, self.old_syntax, changeset.is_replay
                    )
                if self.filechange.new_sha1:
                    new_version = ranges.add_file_version(
                        self.filechange.new_sha1, self.new_syntax, False
                    )

                for macro_chunk in macro_chunks:
                    if old_version and macro_chunk.old_count:
                        macro_chunk.old_range = old_version.add_line_range(
                            macro_chunk.old_offset, macro_chunk.old_end
                        )
                    if new_version and macro_chunk.new_count:
                        macro_chunk.new_range = new_version.add_line_range(
                            macro_chunk.new_offset, macro_chunk.new_end
                        )

                await ranges.fetch()

            self.__macro_chunks = [macro_chunk.create() for macro_chunk in macro_chunks]

        return self.__macro_chunks


# Note: All FileChange objects are automatically valid "ids". If one doesn't
#       resolve to the expected database rows, it means the content difference
#       hasn't been completely processed yet, so a different exception should be
#       raised.
class IncompleteChangeset(public.Delayed):
    def __init__(self) -> None:
        super().__init__("incomplete changeset")


@dataclass
class FetchOne:
    critic: api.critic.Critic

    async def __call__(self, filechange: api.filechange.FileChange) -> Filediff:
        async with api.critic.Query[RowType](
            self.critic,
            """SELECT csf.file,
                      csfd.old_is_binary, csfd.old_length, csfd.old_linebreak,
                      old_hll.label,
                      csfd.new_is_binary, csfd.new_length, csfd.new_linebreak,
                      new_hll.label
                FROM changesetfiles AS csf
                JOIN changesetfiledifferences AS csfd ON (
                        csfd.changeset=csf.changeset AND
                        csfd.file=csf.file
                    )
    LEFT OUTER JOIN highlightfiles AS old_hlf ON (
                        old_hlf.id=csfd.old_highlightfile
                    )
    LEFT OUTER JOIN highlightlanguages AS old_hll ON (
                        old_hll.id=old_hlf.language)
    LEFT OUTER JOIN highlightfiles AS new_hlf ON (
                        new_hlf.id=csfd.new_highlightfile
                    )
    LEFT OUTER JOIN highlightlanguages AS new_hll ON (
                        new_hll.id=new_hlf.language)
                WHERE csf.changeset={changeset}
                AND csf.file={file}""",
            changeset=filechange.changeset,
            file=filechange.file,
        ) as result:
            return Filediff(filechange, await result.one(IncompleteChangeset()))


@dataclass
class FetchMultiple:
    critic: api.critic.Critic
    changeset: api.changeset.Changeset

    async def __call__(
        self, filechanges: Sequence[api.filechange.FileChange]
    ) -> Sequence[Filediff]:
        filechange_by_file_id = {
            filechange.file.id: filechange for filechange in filechanges
        }

        async with api.critic.Query[RowType](
            self.critic,
            """SELECT csf.file,
                    csfd.old_is_binary, csfd.old_length, csfd.old_linebreak,
                    old_hll.label,
                    csfd.new_is_binary, csfd.new_length, csfd.new_linebreak,
                    new_hll.label
                FROM changesetfiles AS csf
                JOIN changesetfiledifferences AS csfd ON (
                        csfd.changeset=csf.changeset AND
                        csfd.file=csf.file
                    )
    LEFT OUTER JOIN highlightfiles AS old_hlf ON (
                        old_hlf.id=csfd.old_highlightfile
                    )
    LEFT OUTER JOIN highlightlanguages AS old_hll ON (
                        old_hll.id=old_hlf.language
                    )
    LEFT OUTER JOIN highlightfiles AS new_hlf ON (
                        new_hlf.id=csfd.new_highlightfile
                    )
    LEFT OUTER JOIN highlightlanguages AS new_hll ON (
                        new_hll.id=new_hlf.language
                    )
                WHERE csf.changeset={changeset}
                AND {csf.file=file_ids:array}""",
            changeset=self.changeset,
            file_ids=list(filechange_by_file_id.keys()),
        ) as result:
            return [
                Filediff(filechange_by_file_id[row[0]], row) async for row in result
            ]


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, filechange: api.filechange.FileChange
) -> PublicType:
    if not await filechange.changeset.ensure_completion_level(
        "changedlines", block=False
    ):
        raise public.Delayed("not finished")

    return await Filediff.ensureOne(filechange, FetchOne(critic))


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, filechanges: Sequence[api.filechange.FileChange]
) -> Sequence[PublicType]:
    # APIObject.cachedMany should short-cut empty requests.
    if not filechanges:
        return []

    # All FileChange objects are guaranteed to be from the same Changeset,
    # either by public.fetchMany() or because we're called from fetchAll()
    # which uses `changeset.files` as the argument.
    changeset = filechanges[0].changeset

    if not await changeset.ensure_completion_level("changedlines", block=False):
        raise public.Delayed("not finished")

    return await Filediff.ensure(filechanges, FetchMultiple(critic, changeset))


@public.fetchAllImpl
async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[PublicType]:
    files = await changeset.files
    if files is None:
        raise IncompleteChangeset()
    return await fetchMany(changeset.critic, files)
