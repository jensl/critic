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

import itertools
from typing import Callable, Collection, Tuple, Optional, Sequence

from critic import api
from critic.api import repositoryfilter as public
from critic import reviewing
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.RepositoryFilter
ArgumentsType = Tuple[int, int, int, str, api.repositoryfilter.FilterType, bool]


class RepositoryFilter(PublicType, APIObjectImplWithId, module=public):
    __delegates: Optional[Collection[api.user.User]]
    __scopes: Optional[Collection[api.reviewscope.ReviewScope]]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__subject_id,
            self.__repository_id,
            self.__path,
            self.__type,
            self.__default_scope,
        ) = args

        self.__delegates = None
        self.__scopes = None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    async def subject(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__subject_id)

    @property
    def type(self) -> public.FilterType:
        return self.__type

    @property
    def path(self) -> str:
        return self.__path

    @property
    def default_scope(self) -> bool:
        return self.__default_scope

    @property
    async def scopes(self) -> Collection[api.reviewscope.ReviewScope]:
        if self.__scopes is None:
            self.__scopes = await api.reviewscope.fetchAll(self.critic, filter=self)
        return self.__scopes

    @property
    async def delegates(self) -> Collection[api.user.User]:
        if self.__delegates is None:
            async with api.critic.Query[int](
                self.critic,
                """SELECT uid
                     FROM repositoryfilterdelegates
                    WHERE filter={filter}""",
                filter=self,
            ) as result:
                user_ids = await result.scalars()
            self.__delegates = frozenset(
                await api.user.fetchMany(self.critic, user_ids)
            )
        return self.__delegates

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "uid",
    "repository",
    "path",
    "type",
    "default_scope",
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, filter_id: int) -> PublicType:
    return await RepositoryFilter.ensureOne(
        filter_id, queries.idFetcher(critic, RepositoryFilter)
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    review: Optional[api.review.Review],
    user: Optional[api.user.User],
    file: Optional[api.file.File],
    scope: Optional[api.reviewscope.ReviewScope],
) -> Sequence[PublicType]:
    conditions = []
    if repository or review:
        conditions.append("repository={repository}")
        if review:
            repository = await review.repository
    if user:
        conditions.append("uid={user}")
    if scope:
        conditions.append("scope={scope}")
    filters = RepositoryFilter.store(
        await queries.query(
            critic, *conditions, repository=repository, user=user, scope=scope
        ).make(RepositoryFilter)
    )
    if review or file:
        evaluator = reviewing.filters.Filters()
        if review:
            evaluator.setFiles(await review.files)
        else:
            assert file is not None
            evaluator.setFiles([file])
        await evaluator.addFilters(filters)
        if not evaluator.matching_filters:
            return []
        matching_filters = set(itertools.chain(*evaluator.matching_filters.values()))
        return [filter for filter in filters if filter in matching_filters]
    return filters
