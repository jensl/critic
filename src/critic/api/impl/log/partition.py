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
from dataclasses import dataclass
from typing import Optional, Any, Iterable, List, Tuple

logger = logging.getLogger(__name__)

from .. import apiobject
from critic import api

WrapperType = api.log.partition.Partition


@dataclass(frozen=True)
class Edge:
    rebase: api.log.rebase.Rebase
    partition: WrapperType


class Partition(apiobject.APIObject[WrapperType, api.commitset.CommitSet, Any]):
    wrapper_class = api.log.partition.Partition

    preceding: Optional[WrapperType.Edge]
    following: Optional[WrapperType.Edge]

    def __init__(self, commits: api.commitset.CommitSet) -> None:
        assert not commits or len(commits.heads) == 1

        self.commits = commits
        self.preceding = None
        self.following = None


async def create(
    critic: api.critic.Critic,
    commits: api.commitset.CommitSet,
    rebases: Iterable[api.log.rebase.Rebase],
) -> WrapperType:
    if not commits:
        return Partition(api.commitset.empty(critic)).wrap(critic)

    original_commits = commits

    partitions: List[Tuple[api.log.rebase.Rebase, WrapperType]] = []

    def add(
        rebase: Optional[api.log.rebase.Rebase], partition: WrapperType
    ) -> WrapperType:
        if partitions:
            previous_rebase, previous_partition = partitions[-1]
            previous_partition._impl.preceding = Edge(previous_rebase, partition)
            partition._impl.following = Edge(previous_rebase, previous_partition)
        if rebase:
            partitions.append((rebase, partition))
        return partition

    all_rebases = list(rebases)
    rebase = None

    for rebase in reversed(all_rebases):
        branchupdate = await rebase.branchupdate
        assert branchupdate  # All rebases must have been performed.
        from_head = await branchupdate.from_head
        assert from_head
        partition_commits = commits.getAncestorsOf(
            from_head, include_self=from_head in commits
        )
        commits = commits - partition_commits
        add(rebase, Partition(partition_commits).wrap(critic))

    if len(commits.heads) > 1:
        if all_rebases:
            logger.error("review=%r", await all_rebases[0].review)
        logger.error("heads=%r", list(original_commits.heads))
        for rebase in all_rebases:
            branchupdate = await rebase.branchupdate
            assert branchupdate  # All rebases must have been performed.
            from_head = await branchupdate.from_head
            to_head = await branchupdate.to_head
            logger.error(
                "rebase=%r, from_head=%r, to_head=%r", rebase, from_head, to_head
            )
        raise api.log.partition.Error("Incompatible commits/rebases arguments")

    return add(None, Partition(commits).wrap(critic))
