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
from typing import Collection, Optional, Iterable, List, Tuple

logger = logging.getLogger(__name__)

from .apiobject import APIObjectImpl
from critic import api
from critic.api import partition as public
from critic.api.apiobject import Actual

PublicType = public.Partition


@dataclass(frozen=True)
class Edge:
    __rebase: api.rebase.Rebase
    __partition: PublicType

    @property
    def rebase(self) -> api.rebase.Rebase:
        return self.__rebase

    @property
    def partition(self) -> PublicType:
        return self.__partition


class Partition(PublicType, APIObjectImpl, module=public):
    wrapper_class = api.partition.Partition

    __preceding: Optional[PublicType.Edge]
    __following: Optional[PublicType.Edge]

    def __init__(self, commits: api.commitset.CommitSet) -> None:
        assert not commits or len(commits.heads) == 1

        self.__commits = commits
        self.__preceding = None
        self.__following = None

    def getCacheKeys(self) -> Collection[object]:
        return ()

    async def refresh(self: Actual) -> Actual:
        return self

    def setPreceding(self, rebase: api.rebase.Rebase, partition: Partition) -> None:
        self.__preceding = Edge(rebase, partition)

    def setFollowing(self, rebase: api.rebase.Rebase, partition: Partition) -> None:
        self.__following = Edge(rebase, partition)

    @property
    def preceding(self) -> Optional[Partition.Edge]:
        return self.__preceding

    @property
    def following(self) -> Optional[Partition.Edge]:
        """The edge leading to the following (older) partition"""
        return self.__following

    @property
    def commits(self) -> api.commitset.CommitSet:
        return self.__commits


@public.createImpl
async def create(
    critic: api.critic.Critic,
    commits: api.commitset.CommitSet,
    rebases: Iterable[api.rebase.Rebase],
) -> PublicType:
    if not commits:
        return Partition(api.commitset.empty(critic))

    original_commits = commits

    partitions: List[Tuple[api.rebase.Rebase, Partition]] = []

    def add(rebase: Optional[api.rebase.Rebase], partition: Partition) -> Partition:
        if partitions:
            previous_rebase, previous_partition = partitions[-1]
            previous_partition.setPreceding(previous_rebase, partition)
            partition.setFollowing(previous_rebase, previous_partition)
        if rebase:
            partitions.append((rebase, partition))
        return partition

    all_rebases = [*rebases]
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
        add(rebase, Partition(partition_commits))

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
        raise api.partition.Error("Incompatible commits/rebases arguments")

    return add(None, Partition(commits))
