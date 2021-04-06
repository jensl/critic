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
from typing import Collection, Optional, Tuple, FrozenSet, Dict, Sequence, Iterator

logger = logging.getLogger(__name__)

from critic import api
from critic.api import mergeanalysis as public
from critic.api.apiobject import Actual
from .apiobject import APIObjectImpl


def filter_blocks(
    primary_blocks: Sequence[api.filediff.ChangedLines],
    reference_blocks: Sequence[api.filediff.ChangedLines],
    adjacency_limit: int,
) -> Iterator[int]:
    primary_blocks_iter = iter(primary_blocks)
    reference_blocks_iter = iter(reference_blocks)

    try:
        primary_block = next(primary_blocks_iter)
        reference_block = next(reference_blocks_iter)

        primary_offset = reference_offset = 0

        while True:
            primary_block_begin = primary_offset + primary_block.offset
            primary_block_end = primary_block_begin + primary_block.delete_length
            reference_block_begin = reference_offset + reference_block.offset
            reference_block_end = reference_block_begin + reference_block.insert_length

            if reference_block_end + adjacency_limit < primary_block_begin:
                reference_offset = reference_block_end
                reference_block = next(reference_blocks_iter)
            else:
                if primary_block_end + adjacency_limit >= reference_block_begin:
                    yield primary_block.index
                primary_offset = primary_block_end
                primary_block = next(primary_blocks_iter)
    except StopIteration:
        # We ran out of either primary or reference blocks. In either case, we
        # shouldn't emit any more blocks; if we ran out of blocks there's
        # nothing more we could emit and if we ran out of reference blocks
        # there's no more reference blocks that could trigger emission of a
        # nearby block.
        pass


ArgumentsType = Tuple[
    api.commit.Commit,
    api.commit.Commit,
    api.changeset.Changeset,
    api.changeset.Changeset,
]


class MergeChangeset(public.MergeChangeset, APIObjectImpl, module=public):
    wrapper_class = api.mergeanalysis.MergeChangeset

    __files: Optional[FrozenSet[api.file.File]]

    def __init__(
        self,
        merge: api.commit.Commit,
        parent: api.commit.Commit,
        primary_changeset: api.changeset.Changeset,
        reference_changeset: api.changeset.Changeset,
    ):
        super().__init__(merge.critic)
        self.__merge = merge
        self.__parent = parent
        self.__primary_changeset = primary_changeset
        self.__reference_changeset = reference_changeset
        self.__files = None

    def __repr__(self) -> str:
        return f"MergeChangeset(merge={self.merge!r}, parent={self.parent!r})"

    def getCacheKeys(self) -> Collection[object]:
        return ((self.__merge, self.__parent),)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def merge(self) -> api.commit.Commit:
        return self.__merge

    @property
    def parent(self) -> api.commit.Commit:
        return self.__parent

    @property
    async def files(self) -> Optional[FrozenSet[api.file.File]]:
        if self.__files is None:
            primary_files = await self.__primary_changeset.files
            if primary_files is None:
                return None
            self.__files = frozenset(filechange.file for filechange in primary_files)
        return self.__files

    async def getMacroChunks(
        self, *, adjacency_limit: int = 2, context_lines: int = 3
    ) -> Dict[api.file.File, Sequence[api.filediff.MacroChunk]]:
        result: Dict[api.file.File, Sequence[api.filediff.MacroChunk]] = {}

        async def get_filediff(
            changeset: api.changeset.Changeset, file: api.file.File
        ) -> api.filediff.Filediff:
            filechange = await api.filechange.fetch(changeset, file)
            return await api.filediff.fetch(filechange)

        files = await self.files

        if files is None:
            return result

        for file in files:
            primary_filediff = await get_filediff(self.__primary_changeset, file)
            reference_filediff = await get_filediff(self.__reference_changeset, file)

            included_indexes = set(
                filter_blocks(
                    await primary_filediff.changed_lines,
                    await reference_filediff.changed_lines,
                    adjacency_limit,
                )
            )

            if not included_indexes:
                continue

            chunks = await primary_filediff.getMacroChunks(
                context_lines,
                block_filter=lambda block: block.index in included_indexes,
            )

            if chunks is not None:
                result[file] = chunks

        return result

    async def ensure_availability(self, *, block: bool = True) -> bool:
        primary_ready = await self.__primary_changeset.ensure_completion_level(
            block=block
        )
        reference_ready = await self.__reference_changeset.ensure_completion_level(
            "changedlines", block=block
        )
        return primary_ready and reference_ready


PublicType = public.MergeAnalysis


class MergeAnalysis(PublicType, APIObjectImpl, module=public):
    __replay: Optional[api.commit.Commit]

    def __init__(self, merge: api.commit.Commit):
        self.__merge = merge
        self.__replay = None

    def getCacheKeys(self) -> Collection[object]:
        return ((self.__merge, self.__replay),)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def merge(self) -> api.commit.Commit:
        return self.__merge

    @property
    async def changes_relative_parents(self) -> Sequence[public.MergeChangeset]:
        changesets = []

        async with api.transaction.start(self.critic) as transaction:
            for parent in await self.merge.parents:
                (
                    primary_modifier,
                    reference_modifier,
                ) = await transaction.ensureMergeChangeset(parent, self.merge)

                await primary_modifier.requestContent()
                await primary_modifier.requestHighlight()
                primary_changeset = primary_modifier.subject

                await reference_modifier.requestContent()
                reference_changeset = reference_modifier.subject

                changesets.append(
                    MergeChangeset(
                        self.merge, parent, primary_changeset, reference_changeset
                    )
                )

        return changesets

    @property
    async def conflict_resolutions(self) -> api.changeset.Changeset:
        if self.__replay is None:
            raise api.mergeanalysis.Error("NOT IMPLEMENTED")
            # self.__replay = await mergereplay.request(self.merge)
            # if self.__replay is None:
            #     raise api.mergeanalysis.Delayed()
        return await api.changeset.fetch(
            self.critic, from_commit=self.__replay, to_commit=self.merge, conflicts=True
        )

    async def ensure_availability(self, *, block: bool = True) -> bool:
        conflict_resolutions = await self.conflict_resolutions
        if not await conflict_resolutions.ensure_completion_level(block=block):
            return False
        for changeset in await self.changes_relative_parents:
            if not await changeset.ensure_availability(block=block):
                return False
        return True


async def fetch(merge: api.commit.Commit) -> PublicType:
    if not merge.is_merge:
        raise api.mergeanalysis.Error("commit is not a merge")
    return MergeAnalysis(merge)
