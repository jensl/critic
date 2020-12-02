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
from typing import Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api import branch as public
from . import apiobject


WrapperType = api.branch.Branch
ArgumentsType = Tuple[
    int, str, int, int, Optional[int], api.branch.BranchType, bool, bool, int
]


class Branch(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    table_name = "branches"
    column_names = [
        "id",
        "name",
        "repository",
        "head",
        "base",
        "type",
        "archived",
        "merged",
        "size",
    ]

    __commits: Optional[api.commitset.CommitSet]

    def __init__(
        self,
        args: ArgumentsType,
    ):
        (
            self.id,
            self.name,
            self.__repository_id,
            self.__head_id,
            self.__base_branch_id,
            self.type,
            self.is_archived,
            self.is_merged,
            self.size,
        ) = args
        self.__commits = None

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)

    async def getBaseBranch(
        self, critic: api.critic.Critic
    ) -> Optional[api.branch.Branch]:
        if self.__base_branch_id is None:
            return None
        return await api.branch.fetch(critic, self.__base_branch_id)

    async def getHead(self, wrapper: WrapperType) -> api.commit.Commit:
        return await api.commit.fetch(await wrapper.repository, self.__head_id)

    async def getCommits(self, wrapper: WrapperType) -> api.commitset.CommitSet:
        if self.__commits is None:
            # Use a more efficient way to fetch all commits from the repository
            # for normal branches that have no base branch and thus simply
            # contain all commits reachable from their head.
            #
            # Review branches never have a base branch assigned, so for them,
            # this optimization is never valid.
            if self.type == "normal" and self.__base_branch_id is None:
                self.__commits = await api.commit.fetchRange(
                    to_commit=await wrapper.head
                )
            else:
                critic = wrapper.critic
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
                    await api.commit.fetchMany(await wrapper.repository, commit_ids),
                )
            assert self.size == len(self.__commits)
        return self.__commits


@public.fetchImpl
@Branch.cached
async def fetch(
    critic: api.critic.Critic,
    branch_id: Optional[int],
    repository: Optional[api.repository.Repository],
    name: Optional[str],
) -> api.branch.Branch:
    if branch_id is not None:
        conditions = ["{id=branch_id}"]
    else:
        conditions = ["{repository=repository}", "{name=name}"]
    async with Branch.query(
        critic,
        conditions,
        branch_id=branch_id,
        repository=repository,
        name=name,
    ) as result:
        try:
            return await Branch.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if branch_id is not None:
                raise api.branch.InvalidId(invalid_id=branch_id)
            else:
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
) -> Sequence[WrapperType]:
    tables = [Branch.table()]
    conditions = ["TRUE"]
    order_by = ["name ASC"] if order == "name" else ["id ASC"]
    if repository:
        conditions.append("repository={repository_id}")
    if created_by or updated_by or order == "update":
        tables.append("JOIN branchupdates ON (branchupdates.branch=branches.id)")
        if created_by:
            conditions.append("branchupdates.updater={created_by_id}")
            conditions.append("branchupdates.from_head IS NULL")
        elif updated_by:
            conditions.append("branchupdates.updater={updated_by_id}")
            conditions.append("branchupdates.from_head IS NOT NULL")
        order_by.insert(0, "branchupdates.updated_at DESC")
    if branch_type is not None:
        conditions.append("branches.type={branch_type}")
    if exclude_reviewed_branches:
        tables.extend(
            [
                "LEFT OUTER JOIN reviewcommits"
                " ON (reviewcommits.commit=branches.head)",
                "LEFT OUTER JOIN reviews" " ON (reviews.id=reviewcommits.review)",
            ]
        )
        conditions.append("(reviews.state IS NULL OR reviews.state='dropped')")
    import re

    logger.debug(
        re.sub(
            r"\s+",
            " ",
            f"""SELECT {Branch.columns()}
              FROM {" ".join(tables)}
             WHERE {" AND ".join(conditions)}
          ORDER BY {", ".join(order_by)}""",
        )
    )
    async with Branch.query(
        critic,
        f"""SELECT {Branch.columns()}
              FROM {" ".join(tables)}
             WHERE {" AND ".join(conditions)}
          ORDER BY {", ".join(order_by)}""",
        repository_id=repository,
        created_by_id=created_by,
        updated_by_id=updated_by,
        branch_type=branch_type,
    ) as result:
        return await Branch.make(critic, result)
