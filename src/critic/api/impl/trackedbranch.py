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
from datetime import datetime
from typing import Callable, Tuple, Optional, Sequence

from critic import api
from critic.api import trackedbranch as public
from critic.api.impl.queryhelper import QueryHelper, QueryResult, join
from .apiobject import APIObjectImplWithId


@dataclass(frozen=True)
class Source:
    __url: str
    __name: str

    @property
    def url(self) -> str:
        return self.__url

    @property
    def name(self) -> str:
        return self.__name


PublicType = public.TrackedBranch
ArgumentsType = Tuple[
    int, int, str, str, str, bool, bool, Optional[datetime], Optional[datetime]
]


class TrackedBranch(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__repository_id,
            self.__name,
            source_url,
            source_name,
            self.__is_forced,
            self.__is_disabled,
            self.__last_update,
            self.__next_update,
        ) = args

        self.__source = Source(source_url, source_name)
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def is_disabled(self) -> bool:
        return self.__is_disabled

    @property
    def is_forced(self) -> bool:
        return self.__is_forced

    @property
    def name(self) -> str:
        return self.__name

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    def source(self) -> PublicType.Source:
        return self.__source

    @property
    def last_update(self) -> Optional[datetime]:
        return self.__last_update

    @property
    def next_update(self) -> Optional[datetime]:
        return self.__next_update

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    TrackedBranch.getTableName(),
    "id",
    "repository",
    "local_name",
    "remote",
    "remote_name",
    "forced",
    "disabled",
    "previous",
    "next",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    trackedbranch_id: Optional[int],
    repository: Optional[api.repository.Repository],
    name: Optional[str],
    branch: Optional[api.branch.Branch],
    review: Optional[api.review.Review],
) -> PublicType:
    if trackedbranch_id is not None:
        return await TrackedBranch.ensureOne(
            trackedbranch_id, queries.idFetcher(critic, TrackedBranch)
        )

    if review:
        branch = await review.branch
    if branch:
        repository = await branch.repository
        name = branch.name

    assert repository is not None and name is not None
    return TrackedBranch.storeOne(
        await queries.query(critic, repository=repository, local_name=name).makeOne(
            TrackedBranch, public.NotFound()
        )
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    include_review_branches: bool,
) -> Sequence[PublicType]:
    conditions = []
    joins = []
    if repository is not None:
        conditions.append("trackedbranches.repository={repository}")
    if not include_review_branches:
        conditions.append("branches.type!='review'")
        joins.append(
            join(
                branches=[
                    "branches.repository=trackedbranches.repository",
                    "branches.name=trackedbranches.local_name",
                ]
            )
        )
    return TrackedBranch.store(
        await queries.query(
            critic, queries.formatQuery(*conditions, joins=joins), repository=repository
        ).make(TrackedBranch)
    )
