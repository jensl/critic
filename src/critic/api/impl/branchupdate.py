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
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic.api import branchupdate as public
from . import apiobject


WrapperType = api.branchupdate.BranchUpdate
ArgumentsType = Tuple[
    int,
    int,
    Optional[int],
    Optional[int],
    int,
    datetime.datetime,
    Optional[str],
]


class BranchUpdate(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.branchupdate.BranchUpdate
    column_names = [
        "id",
        "branch",
        "updater",
        "from_head",
        "to_head",
        "updated_at",
        "output",
    ]

    __associated_commits: Optional[api.commitset.CommitSet]
    __disassociated_commits: Optional[api.commitset.CommitSet]
    __commits: Optional[api.commitset.CommitSet]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__branch_id,
            self.__updater_id,
            self.__from_head_id,
            self.__to_head_id,
            self.timestamp,
            self.output,
        ) = args
        self.__associated_commits = None
        self.__disassociated_commits = None
        self.__commits = None

    async def getBranch(self, critic: api.critic.Critic) -> api.branch.Branch:
        return await api.branch.fetch(critic, self.__branch_id)

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await (await self.getBranch(critic)).repository

    async def getUpdater(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.__updater_id is None:
            return None
        return await api.user.fetch(critic, self.__updater_id)

    async def getFromHead(
        self, critic: api.critic.Critic
    ) -> Optional[api.commit.Commit]:
        if self.__from_head_id is None:
            return None
        return await api.commit.fetch(
            await self.getRepository(critic), self.__from_head_id
        )

    async def getToHead(self, critic: api.critic.Critic) -> api.commit.Commit:
        return await api.commit.fetch(
            await self.getRepository(critic), self.__to_head_id
        )

    async def getAssociatedCommits(
        self, critic: api.critic.Critic
    ) -> api.commitset.CommitSet:
        if self.__associated_commits is None:
            repository = await self.getRepository(critic)
            async with api.critic.Query[int](
                critic,
                """SELECT commit
                     FROM branchupdatecommits
                    WHERE branchupdate={branchupdate_id}
                      AND associated""",
                branchupdate_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            logger.debug(f"{commit_ids=}")
            self.__associated_commits = await api.commitset.create(
                critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__associated_commits

    async def getDisassociatedCommits(
        self, critic: api.critic.Critic
    ) -> api.commitset.CommitSet:
        if self.__disassociated_commits is None:
            repository = await self.getRepository(critic)
            async with api.critic.Query[int](
                critic,
                """SELECT commit
                     FROM branchupdatecommits
                    WHERE branchupdate={branchupdate_id}
                      AND NOT associated""",
                branchupdate_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            self.__disassociated_commits = await api.commitset.create(
                critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__disassociated_commits

    async def getCommits(self, critic: api.critic.Critic) -> api.commitset.CommitSet:
        if self.__commits is None:
            repository = await self.getRepository(critic)
            commit_ids = set()
            async with api.critic.Query[Tuple[int, bool]](
                critic,
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
                critic, await api.commit.fetchMany(repository, commit_ids)
            )
        return self.__commits


@public.fetchImpl
@BranchUpdate.cached
async def fetch(
    critic: api.critic.Critic,
    branchupdate_id: Optional[int],
    event: Optional[api.reviewevent.ReviewEvent],
) -> WrapperType:
    tables = [BranchUpdate.table()]
    conditions = []
    if branchupdate_id is not None:
        conditions.append("branchupdates.id={branchupdate_id}")
    else:
        assert event
        if event.type != "branchupdate":
            raise api.branchupdate.InvalidReviewEvent(event)
        tables.append("reviewupdates ON (reviewupdates.branchupdate=branchupdates.id)")
        conditions.append("reviewupdates.event={event}")
    async with BranchUpdate.query(
        critic, conditions, branchupdate_id=branchupdate_id, event=event
    ) as result:
        return await BranchUpdate.makeOne(critic, result)


@public.fetchManyImpl
@BranchUpdate.cachedMany
async def fetchMany(
    critic: api.critic.Critic, branchupdate_ids: Sequence[int]
) -> Sequence[WrapperType]:
    async with BranchUpdate.query(
        critic,
        ["branchupdates.id=ANY({branchupdate_ids})"],
        branchupdate_ids=branchupdate_ids,
    ) as result:
        return await BranchUpdate.make(critic, result)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    branch: Optional[api.branch.Branch],
    updater: Optional[api.user.User],
) -> Sequence[WrapperType]:
    conditions = []
    if branch is not None:
        conditions.append("branch={branch}")
    if updater is not None:
        conditions.append("updater={updater}")
    async with BranchUpdate.query(
        critic, conditions, order_by="id DESC", branch=branch, updater=updater
    ) as result:
        return await BranchUpdate.make(critic, result)
