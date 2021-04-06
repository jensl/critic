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

from critic.background.differenceengine import changedfile

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic import pubsub

from . import Key, protocol
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
        file_id = self.changed_file.file_id
        assert file_id is not None
        key: Key = (file_id,) + tuple(
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
        path = self.changed_file.path
        old_sha1 = self.changed_file.required_old_sha1
        old_encodings = self.group.as_changeset.decode_old.getFileContentEncodings(path)
        new_sha1 = self.changed_file.required_new_sha1
        new_encodings = self.group.as_changeset.decode_new.getFileContentEncodings(path)

        pubsub_client = await self.service.pubsub_client

        return [
            await pubsub_client.request(
                pubsub.Payload(
                    protocol.AnalyzeChangedLines.Request(
                        self.group.as_changeset.changeset_id,
                        self.changed_file.required_file_id,
                        protocol.Source(
                            self.group.repository_path,
                            old_encodings,
                            old_sha1,
                        ),
                        protocol.Source(
                            self.group.repository_path,
                            new_encodings,
                            new_sha1,
                        ),
                        [
                            protocol.Block(
                                block.index,
                                block.delete_offset,
                                block.delete_length,
                                block.insert_offset,
                                block.insert_length,
                            )
                            for block in self.blocks
                        ],
                    )
                ),
                pubsub.ChannelName("analyzechangedlines"),
            )
        ]

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
