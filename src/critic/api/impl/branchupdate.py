# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import datetime
import logging
from typing import Callable, Optional, Sequence, Tuple

from .queryhelper import QueryHelper, QueryResult, join

logger = logging.getLogger(__name__)

from critic import api, dbaccess
from critic.api import branchupdate as public
from .apiobject import APIObjectImplWithId


PublicType = api.branchupdate.BranchUpdate
ArgumentsType = Tuple[
    int,
    int,
    Optional[int],
    Optional[int],
    int,
    datetime.datetime,
    Optional[str],
]


class BranchUpdate(PublicType, APIObjectImplWithId, module=public):
    __associated_commits: Optional[api.commitset.CommitSet]
    __disassociated_commits: Optional[api.commitset.CommitSet]
    __commits: Optional[api.commitset.CommitSet]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__branch_id,
            self.__updater_id,
            self.__from_head_id,
            self.__to_head_id,
            self.__timestamp,
            self.__output,
        ) = args
        self.__associated_commits = None
        self.__disassociated_commits = None
        self.__commits = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def branch(self) -> api.branch.Branch:
        return await api.branch.fetch(self.critic, self.__branch_id)

    @property
    async def repository(self) -> api.repository.Repository:
        return await (await self.branch).repository

    @property
    async def updater(self) -> Optional[api.user.User]:
        if self.__updater_id is None:
            return None
        return await api.user.fetch(self.critic, self.__updater_id)

    @property
    async def from_head(self) -> Optional[api.commit.Commit]:
        if self.__from_head_id is None:
            return None
        return await api.commit.fetch(await self.repository, self.__from_head_id)

    @property
    async def to_head(self) -> api.commit.Commit:
        return await api.commit.fetch(await self.repository, self.__to_head_id)

    @property
    async def associated_commits(self) -> api.commitset.CommitSet:
        if self.__associated_commits is None:
            repository = await self.repository
            async with api.critic.Query[int](
                self.critic,
                """SELECT commit
                     FROM branchupdatecommits
                    WHERE branchupdate={branchupdate_id}
                      AND associated""",
                branchupdate_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            self.__associated_commits = await api.commitset.create(
                self.critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__associated_commits

    @property
    async def disassociated_commits(self) -> api.commitset.CommitSet:
        if self.__disassociated_commits is None:
            repository = await self.repository
            async with api.critic.Query[int](
                self.critic,
                """SELECT commit
                     FROM branchupdatecommits
                    WHERE branchupdate={branchupdate_id}
                      AND NOT associated""",
                branchupdate_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            self.__disassociated_commits = await api.commitset.create(
                self.critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__disassociated_commits

    @property
    async def commits(self) -> api.commitset.CommitSet:
        if self.__commits is None:
            repository = await self.repository
            commit_ids = set()
            async with api.critic.Query[Tuple[int, bool]](
                self.critic,
                """SELECT commit, associated
                     FROM branchupdates
                     JOIN branchupdatecommits ON (
                            branchupdate=branchupdates.id
                          )
                    WHERE branch={branch_id}
                      AND branchupdate<={branchupdate_id}
                 ORDER BY branchupdate ASC""",
                branch_id=self.__branch_id,
                branchupdate_id=self.id,
            ) as result:
                async for commit_id, was_associated in result:
                    if was_associated:
                        commit_ids.add(commit_id)
                    else:
                        commit_ids.remove(commit_id)
            self.__commits = await api.commitset.create(
                self.critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__commits

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    @property
    def output(self) -> Optional[str]:
        return self.__output

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "branch",
    "updater",
    "from_head",
    "to_head",
    "updated_at",
    "output",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    branchupdate_id: Optional[int],
    event: Optional[api.reviewevent.ReviewEvent],
) -> PublicType:
    if branchupdate_id is not None:
        return await BranchUpdate.ensureOne(
            branchupdate_id, queries.idFetcher(critic, BranchUpdate)
        )
    assert event
    if event.type != "branchupdate":
        raise api.branchupdate.InvalidReviewEvent(event)
    try:
        return BranchUpdate.storeOne(
            await queries.query(
                critic,
                queries.formatQuery(
                    "reviewupdates.event={event}",
                    joins=[
                        join(
                            reviewupdates=[
                                "reviewupdates.branchupdate=branchupdates.id"
                            ],
                        )
                    ],
                ),
            ).makeOne(BranchUpdate)
        )
    except dbaccess.ZeroRowsInResult:
        raise public.InvalidReviewEvent(event)


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, branchupdate_ids: Sequence[int]
) -> Sequence[PublicType]:
    return await BranchUpdate.ensure(
        branchupdate_ids, queries.idsFetcher(critic, BranchUpdate)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    branch: Optional[api.branch.Branch],
    updater: Optional[api.user.User],
) -> Sequence[PublicType]:
    return BranchUpdate.store(
        await queries.query(critic, branch=branch, updater=updater).make(BranchUpdate)
    )
