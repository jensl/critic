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
from typing import Callable, Optional, Tuple, Sequence

from critic.api.impl.queryhelper import QueryHelper, QueryResult

logger = logging.getLogger(__name__)

from critic import api
from critic.api import rebase as public
from .apiobject import APIObjectImplWithId

PublicType = public.Rebase
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


class Rebase(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__review_id,
            self.__creator_id,
            self.__branchupdate_id,
            _,
            _,
            _,
            _,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    def is_pending(self) -> bool:
        return self.__branchupdate_id is None

    @property
    async def repository(self) -> api.repository.Repository:
        return await (await self.review).repository

    @property
    async def branchupdate(self) -> Optional[api.branchupdate.BranchUpdate]:
        if self.__branchupdate_id is None:
            return None
        return await api.branchupdate.fetch(self.critic, self.__branchupdate_id)

    @property
    async def creator(self) -> api.user.User:
        if self.__creator_id is None:
            return api.user.system(self.critic)
        return await api.user.fetch(self.critic, self.__creator_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "review",
    "uid",
    "branchupdate",
    "old_upstream",
    "new_upstream",
    "equivalent_merge",
    "replayed_rebase",
)


class HistoryRewrite(public.HistoryRewrite, Rebase, module=public):
    pass


class MoveRebase(public.MoveRebase, Rebase, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            _,
            _,
            _,
            _,
            self.__old_upstream_id,
            self.__new_upstream_id,
            self.__equivalent_merge_id,
            self.__replayed_rebase_id,
        ) = args
        return super().update(args)

    async def __getCommit(self, commit_id: int) -> api.commit.Commit:
        return await api.commit.fetch(await self.repository, commit_id)

    @property
    async def old_upstream(self) -> api.commit.Commit:
        assert self.__old_upstream_id is not None
        return await self.__getCommit(self.__old_upstream_id)

    @property
    async def new_upstream(self) -> api.commit.Commit:
        assert self.__new_upstream_id is not None
        return await self.__getCommit(self.__new_upstream_id)

    @property
    async def equivalent_merge(self) -> Optional[api.commit.Commit]:
        assert self.__new_upstream_id is not None
        if self.__equivalent_merge_id is None:
            return None
        return await self.__getCommit(self.__equivalent_merge_id)

    @property
    async def replayed_rebase(self) -> Optional[api.commit.Commit]:
        assert self.__new_upstream_id is not None
        if self.__replayed_rebase_id is None:
            return None
        return await self.__getCommit(self.__replayed_rebase_id)


def make(critic: api.critic.Critic, args: ArgumentsType) -> Rebase:
    new_upstream_id = args[5]
    return (
        HistoryRewrite(critic, args)
        if new_upstream_id is None
        else MoveRebase(critic, args)
    )


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    rebase_id: Optional[int],
    branchupdate: Optional[api.branchupdate.BranchUpdate],
) -> PublicType:
    if rebase_id is not None:
        return await Rebase.ensureOne(rebase_id, queries.idFetcher(critic, make))

    assert branchupdate
    return Rebase.storeOne(
        await queries.query(critic, branchupdate=branchupdate).makeOne(
            make, api.rebase.NotARebase(branchupdate)
        )
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, review: Optional[api.review.Review], pending: bool
) -> Sequence[PublicType]:
    conditions = []
    if review is not None:
        conditions.append("review={review}")
    if pending:
        conditions.append("branchupdate IS NULL")
    else:
        conditions.append("branchupdate IS NOT NULL")
    return Rebase.store(
        await queries.query(critic, *conditions, review=review).make(make)
    )
