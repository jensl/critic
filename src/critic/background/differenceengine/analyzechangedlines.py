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
import logging
from typing import Collection, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import diff
from critic import gitaccess
from critic import pubsub

from . import protocol
from .changedfile import ChangedFile
from .changedlines import ChangedLines
from .requestjob import RequestJob, GroupType


class AnalyzeChangedLines(RequestJob[protocol.AnalyzeChangedLines.Response]):
    # Analyze changed lines after calculating file difference in all files.
    # This improves progress feedback, since we'll know the total number of
    # blocks of changed lines to analyze sooner.
    priority = 2  # CalculateFileDifference.priority + 1

    # Failure to analyze a block of changed lines is non-fatal; we can just
    # display a stupid diff with the block top-aligned on both sides and without
    # inter-line difference.
    is_fatal = False

    def __init__(
        self,
        group: GroupType,
        changed_file: ChangedFile,
        blocks: Sequence[ChangedLines],
    ):
        self.changed_file = changed_file
        self.blocks = blocks
        key = (self.changed_file.file_id,) + tuple(
            (block.delete_offset, block.insert_offset) for block in self.blocks
        )
        super().__init__(group, key)

    def split(self) -> Optional[Collection[AnalyzeChangedLines]]:
        if len(self.blocks) <= 1:
            return None
        return [
            AnalyzeChangedLines(self.group, self.changed_file, [block])
            for block in self.blocks
        ]

    async def issue_requests(
        self, client: pubsub.Client
    ) -> Sequence[pubsub.OutgoingRequest]:
        async with self.group.repository() as repository:
            old_blob, new_blob = await repository.fetchall(
                self.changed_file.required_old_sha1,
                self.changed_file.required_new_sha1,
                wanted_object_type="blob",
            )

        assert isinstance(old_blob, gitaccess.GitBlob)
        assert isinstance(new_blob, gitaccess.GitBlob)

        old_lines = diff.parse.splitlines(old_blob.data)
        new_lines = diff.parse.splitlines(new_blob.data)

        pubsub_client = await self.service.pubsub_client

        return await asyncio.gather(
            *(
                pubsub_client.request(
                    pubsub.Payload(
                        protocol.AnalyzeChangedLines.Request(
                            block.extract_old_lines(old_lines),
                            block.extract_new_lines(new_lines),
                        )
                    ),
                    pubsub.ChannelName("analyzechangedlines"),
                )
                for block in self.blocks
            )
        )

    async def update_database(self, critic: api.critic.Critic) -> None:
        assert self.responses is not None and len(self.responses) == len(self.blocks)

        async with critic.transaction() as cursor:
            await cursor.executemany(
                """UPDATE changesetchangedlines
                      SET analysis={analysis}
                    WHERE changeset={changeset_id}
                      AND file={file_id}
                      AND "index"={index}""",
                (
                    dbaccess.parameters(
                        changeset_id=self.group.changeset_id,
                        file_id=self.changed_file.file_id,
                        analysis=response.analysis if response is not None else None,
                        index=block.index,
                    )
                    for response, block in zip(self.responses, self.blocks)
                ),
            )

    @staticmethod
    def for_blocks(
        group: GroupType, changed_file: ChangedFile, blocks: Iterable[ChangedLines]
    ) -> Iterable[AnalyzeChangedLines]:
        # Cost is calculated in terms of pairs of lines to consider.  We spread
        # the work out across multiple jobs to increase parallel processing.
        # Too much parallel processing is not efficient, though; there's
        # overhead in fetching the blob from the repository and splitting it
        # into lines.
        MAXIMUM_COST = 5000

        current_blocks: List[ChangedLines] = []
        current_cost = 0

        def flush() -> AnalyzeChangedLines:
            nonlocal current_blocks
            nonlocal current_cost
            try:
                return AnalyzeChangedLines(group, changed_file, current_blocks)
            finally:
                current_blocks = []
                current_cost = 0

        for block in blocks:
            if not block.delete_length or not block.insert_length:
                continue
            cost = block.delete_length * block.insert_length
            if current_blocks and current_cost + cost > MAXIMUM_COST:
                yield flush()
            current_blocks.append(block)
            current_cost += cost

        if current_blocks:
            yield flush()
