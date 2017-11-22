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
from typing import Optional, Tuple, Sequence

logger = logging.getLogger(__name__)

from critic import api
from .. import apiobject

WrapperType = api.log.rebase.Rebase
ArgumentsType = Tuple[
    int,
    int,
    int,
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
]


class Rebase(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    table_name = "reviewrebases"
    column_names = [
        "id",
        "review",
        "uid",
        "branchupdate",
        "old_upstream",
        "new_upstream",
        "equivalent_merge",
        "replayed_rebase",
    ]

    def __init__(self, args: ArgumentsType) -> None:
        (
            self.id,
            self.review_id,
            self.creator_id,
            self.branchupdate_id,
            self.old_upstream_id,
            self.new_upstream_id,
            self.equivalent_merge_id,
            self.replayed_rebase_id,
        ) = args

        if self.new_upstream_id is None:
            self.wrapper_class = api.log.rebase.HistoryRewrite
        else:
            self.wrapper_class = api.log.rebase.MoveRebase

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.review_id)

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await (await self.getReview(critic)).repository

    async def getBranchUpdate(
        self, critic: api.critic.Critic
    ) -> Optional[api.branchupdate.BranchUpdate]:
        if self.branchupdate_id is None:
            return None
        return await api.branchupdate.fetch(critic, self.branchupdate_id)

    async def __getCommit(
        self, critic: api.critic.Critic, commit_id: int
    ) -> api.commit.Commit:
        return await api.commit.fetch(await self.getRepository(critic), commit_id)

    async def getOldUpstream(self, critic: api.critic.Critic) -> api.commit.Commit:
        assert self.old_upstream_id is not None
        return await self.__getCommit(critic, self.old_upstream_id)

    async def getNewUpstream(self, critic: api.critic.Critic) -> api.commit.Commit:
        assert self.new_upstream_id is not None
        return await self.__getCommit(critic, self.new_upstream_id)

    async def getEquivalentMerge(
        self, critic: api.critic.Critic
    ) -> Optional[api.commit.Commit]:
        assert self.new_upstream_id is not None
        if self.equivalent_merge_id is None:
            return None
        return await self.__getCommit(critic, self.equivalent_merge_id)

    async def getReplayedRebase(
        self, critic: api.critic.Critic
    ) -> Optional[api.commit.Commit]:
        assert self.new_upstream_id is not None
        if self.replayed_rebase_id is None:
            return None
        return await self.__getCommit(critic, self.replayed_rebase_id)

    async def getCreator(self, critic: api.critic.Critic) -> api.user.User:
        if self.creator_id is None:
            return api.user.system(critic)
        return await api.user.fetch(critic, self.creator_id)


@Rebase.cached
async def fetch(
    critic: api.critic.Critic,
    rebase_id: Optional[int],
    branchupdate: Optional[api.branchupdate.BranchUpdate],
) -> WrapperType:
    conditions = []
    if rebase_id is not None:
        conditions.append("id={rebase_id}")
    if branchupdate is not None:
        conditions.append("branchupdate={branchupdate}")
    try:
        async with Rebase.query(
            critic, conditions, rebase_id=rebase_id, branchupdate=branchupdate
        ) as result:
            return await Rebase.makeOne(critic, result)
    except result.ZeroRowsInResult:
        if branchupdate is not None:
            raise api.log.rebase.NotARebase(branchupdate)
        raise


async def fetchAll(
    critic: api.critic.Critic, review: Optional[api.review.Review], pending: bool
) -> Sequence[WrapperType]:
    conditions = []
    if review is not None:
        conditions.append("review={review}")
    if pending:
        conditions.append("branchupdate IS NULL")
    else:
        conditions.append("branchupdate IS NOT NULL")
    async with Rebase.query(
        critic, conditions, review=review, order_by="id DESC"
    ) as result:
        return await Rebase.make(critic, result)
