# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
from typing import Callable, List, Tuple, Optional, Sequence

from .queryhelper import QueryHelper, QueryResult, join, left_outer_join

logger = logging.getLogger(__name__)

from critic import api, dbaccess
from critic.api import branch as public
from .apiobject import APIObjectImplWithId


PublicType = api.branch.Branch
ArgumentsType = Tuple[
    int, str, int, int, Optional[int], api.branch.BranchType, bool, bool, int
]


class Branch(PublicType, APIObjectImplWithId, module=public):
    __commits: Optional[api.commitset.CommitSet]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__name,
            self.__repository_id,
            self.__head_id,
            self.__base_branch_id,
            self.__type,
            self.__is_archived,
            self.__is_merged,
            self.__size,
        ) = args
        self.__commits = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def type(self) -> public.BranchType:
        return self.__type

    @property
    def name(self) -> str:
        return self.__name

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    def is_archived(self) -> bool:
        return self.__is_archived

    @property
    def is_merged(self) -> bool:
        return self.__is_merged

    @property
    def size(self) -> int:
        return self.__size

    @property
    async def base_branch(self) -> Optional[api.branch.Branch]:
        if self.__base_branch_id is None:
            return None
        return await api.branch.fetch(self.critic, self.__base_branch_id)

    @property
    async def head(self) -> api.commit.Commit:
        return await api.commit.fetch(await self.repository, self.__head_id)

    @property
    async def commits(self) -> api.commitset.CommitSet:
        if self.__commits is None:
            # Use a more efficient way to fetch all commits from the repository
            # for normal branches that have no base branch and thus simply
            # contain all commits reachable from their head.
            #
            # Review branches never have a base branch assigned, so for them,
            # this optimization is never valid.
            if self.type == "normal" and self.__base_branch_id is None:
                self.__commits = await api.commit.fetchRange(to_commit=await self.head)
            else:
                critic = self.critic
                async with api.critic.Query[int](
                    critic,
                    """SELECT commit
                         FROM branchcommits
                        WHERE branch={branch_id}""",
                    branch_id=self.id,
                ) as result:
                    commit_ids = await result.scalars()
                self.__commits = await api.commitset.create(
                    critic,
                    await api.commit.fetchMany(await self.repository, commit_ids),
                )
            assert self.size == len(self.__commits)
        return self.__commits

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "name",
    "repository",
    "head",
    "base",
    "type",
    "archived",
    "merged",
    "size",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    branch_id: Optional[int],
    repository: Optional[api.repository.Repository],
    name: Optional[str],
) -> api.branch.Branch:
    if branch_id is not None:
        return await Branch.ensureOne(
            branch_id, queries.idFetcher(critic, Branch), api.branch.InvalidId
        )

    try:
        return Branch.storeOne(
            await queries.query(critic, repository=repository, name=name).makeOne(
                Branch
            )
        )
    except dbaccess.ZeroRowsInResult:
        raise api.branch.InvalidName(value=name)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    created_by: Optional[api.user.User],
    updated_by: Optional[api.user.User],
    branch_type: Optional[api.branch.BranchType],
    exclude_reviewed_branches: bool,
    order: api.branch.Order,
) -> Sequence[PublicType]:
    joins: List[str] = []
    conditions: List[str] = []
    order_by = ["name ASC"] if order == "name" else ["id ASC"]
    if repository:
        conditions.append("repository={repository}")
    if created_by or updated_by or order == "update":
        joins.append(join(branchupdates=["branchupdates.branch=branches.id"]))
        if created_by:
            conditions.append("branchupdates.updater={created_by}")
            conditions.append("branchupdates.from_head IS NULL")
        elif updated_by:
            conditions.append("branchupdates.updater={updated_by}")
            conditions.append("branchupdates.from_head IS NOT NULL")
        order_by.insert(0, "branchupdates.updated_at DESC")
    if branch_type is not None:
        conditions.append("branches.type={branch_type}")
    if exclude_reviewed_branches:
        joins.extend(
            [
                left_outer_join(reviewcommits=["reviewcommits.commit=branches.head"]),
                left_outer_join(reviews=["reviews.id=reviewcommits.review"]),
            ]
        )
        conditions.append("reviews.state IS NULL OR reviews.state='dropped'")
    return Branch.store(
        await queries.query(
            critic,
            queries.formatQuery(*conditions, order_by=order_by, joins=joins),
            repository=repository,
            created_by=created_by,
            updated_by=updated_by,
            branch_type=branch_type,
        ).make(Branch)
    )
