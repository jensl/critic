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

from dataclasses import dataclass
from typing import Tuple, Optional, Sequence

from critic import api
from critic.api import trackedbranch as public
from . import apiobject


@dataclass(frozen=True)
class Source:
    url: str
    name: str


WrapperType = api.trackedbranch.TrackedBranch
ArgumentsType = Tuple[int, int, str, str, str, bool, bool]


class TrackedBranch(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    table_name = "trackedbranches"
    wrapper_class = api.trackedbranch.TrackedBranch
    column_names = [
        "id",
        "repository",
        "local_name",
        "remote",
        "remote_name",
        "forced",
        "disabled",
    ]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__repository_id,
            self.name,
            source_url,
            source_name,
            self.is_forced,
            self.is_disabled,
        ) = args

        self.source = Source(source_url, source_name)

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)


@public.fetchImpl
@TrackedBranch.cached
async def fetch(
    critic: api.critic.Critic,
    trackedbranch_id: Optional[int],
    repository: Optional[api.repository.Repository],
    name: Optional[str],
    branch: Optional[api.branch.Branch],
    review: Optional[api.review.Review],
) -> WrapperType:
    if review:
        branch = await review.branch
    if branch:
        repository = await branch.repository
        name = branch.name
    if repository and name is not None:
        conditions = ["repository={repository}", "local_name={name}"]
    else:
        assert trackedbranch_id is not None
        conditions = ["id={trackedbranch_id}"]

    async with TrackedBranch.query(
        critic,
        conditions,
        trackedbranch_id=trackedbranch_id,
        repository=repository,
        name=name,
    ) as result:
        try:
            return await TrackedBranch.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if repository and name is not None:
                raise api.trackedbranch.NotFound()
            raise


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    include_review_branches: bool,
) -> Sequence[WrapperType]:
    conditions = ["TRUE"]
    if repository is not None:
        conditions.append("repository={repository}")
    if not include_review_branches:
        conditions.append("branches.type!='review'")
    async with TrackedBranch.query(
        critic,
        f"""SELECT {TrackedBranch.columns()}
              FROM {TrackedBranch.table()}
   LEFT OUTER JOIN branches ON (
                     branches.repository=trackedbranches.repository AND
                     branches.name=trackedbranches.local_name
                   )
             WHERE {" AND ".join(conditions)}""",
        repository=repository,
    ) as result:
        return await TrackedBranch.make(critic, result)
