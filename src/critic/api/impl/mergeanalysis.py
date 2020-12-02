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
from typing import Optional, Any, Tuple, FrozenSet, Dict, Sequence, Iterator

logger = logging.getLogger(__name__)

from .apiobject import APIObject
from critic import api


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


class MergeChangeset(APIObject[api.mergeanalysis.MergeChangeset, ArgumentsType, Any]):
    wrapper_class = api.mergeanalysis.MergeChangeset

    __files: Optional[FrozenSet[api.file.File]]

    def __init__(self, args: ArgumentsType) -> None:
        (
            self.merge,
            self.parent,
            self.__primary_changeset,
            self.__reference_changeset,
        ) = args
        self.__files = None

    async def getFiles(
        self, critic: api.critic.Critic
    ) -> Optional[FrozenSet[api.file.File]]:
        if self.__files is None:
            primary_files = await self.__primary_changeset.files
            if primary_files is None:
                return None
            self.__files = frozenset(filechange.file for filechange in primary_files)
        return self.__files

    async def getMacroChunks(
        self, critic: api.critic.Critic, adjacency_limit: int, context_lines: int
    ) -> Dict[api.file.File, Sequence[api.filediff.MacroChunk]]:
        result: Dict[api.file.File, Sequence[api.filediff.MacroChunk]] = {}

        async def get_filediff(
            changeset: api.changeset.Changeset, file: api.file.File
        ) -> api.filediff.Filediff:
            filechange = await api.filechange.fetch(changeset, file)
            return await api.filediff.fetch(filechange)

        files = await self.getFiles(critic)

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

    async def ensure(self, critic: api.critic.Critic, block: bool) -> bool:
        primary_ready = await self.__primary_changeset.ensure(block=block)
        reference_ready = await self.__reference_changeset.ensure(
            "changedlines", block=block
        )
        return primary_ready and reference_ready


WrapperType = api.mergeanalysis.MergeAnalysis


class MergeAnalysis(APIObject[WrapperType, api.commit.Commit, api.commit.Commit]):
    wrapper_class = api.mergeanalysis.MergeAnalysis

    __replay: Optional[api.commit.Commit]

    def __init__(self, merge: api.commit.Commit) -> None:
        self.merge = merge
        self.__replay = None

    async def getChangesRelativeParent(
        self, critic: api.critic.Critic
    ) -> Sequence[api.mergeanalysis.MergeChangeset]:
        from critic.changeset.structure import request_merge

        changesets = []

        for parent in await self.merge.parents:
            primary_changeset_id, reference_changeset_id = await request_merge(
                parent, self.merge
            )

            primary_changeset = await api.changeset.fetch(critic, primary_changeset_id)
            reference_changeset = await api.changeset.fetch(
                critic, reference_changeset_id
            )

            changesets.append(
                MergeChangeset(
                    (self.merge, parent, primary_changeset, reference_changeset)
                ).wrap(critic)
            )

        return changesets

    async def getConflictResolutions(
        self, critic: api.critic.Critic
    ) -> api.changeset.Changeset:
        # from critic.changeset import mergereplay

        if self.__replay is None:
            raise api.mergeanalysis.Error("NOT IMPLEMENTED")
            # self.__replay = await mergereplay.request(self.merge)
            # if self.__replay is None:
            #     raise api.mergeanalysis.Delayed()
        return await api.changeset.fetch(
            critic, from_commit=self.__replay, to_commit=self.merge, conflicts=True
        )

    async def ensure(self, critic: api.critic.Critic, block: bool) -> bool:
        conflict_resolutions = await self.getConflictResolutions(critic)
        if not await conflict_resolutions.ensure(block=block):
            return False
        for changeset in await self.getChangesRelativeParent(critic):
            if not await changeset.ensure(block=block):
                return False
        return True


async def fetch(merge: api.commit.Commit) -> WrapperType:
    if not merge.is_merge:
        raise api.mergeanalysis.Error("commit is not a merge")
    return await MergeAnalysis.makeOne(merge.critic, values=merge)
