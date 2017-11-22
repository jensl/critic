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

from typing import Collection, Tuple, Optional, Sequence, FrozenSet

from . import apiobject
from critic import api

WrapperType = api.repositoryfilter.RepositoryFilter
ArgumentsType = Tuple[int, int, int, str, api.repositoryfilter.FilterType, bool]


class RepositoryFilter(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.repositoryfilter.RepositoryFilter
    column_names = ["id", "uid", "repository", "path", "type", "default_scope"]

    __delegates: Optional[Collection[api.user.User]]
    __scopes: Optional[Collection[api.reviewscope.ReviewScope]]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__subject_id,
            self.__repository_id,
            self.path,
            self.type,
            self.default_scope,
        ) = args

        self.__delegates = None
        self.__scopes = None

    async def getSubject(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__subject_id)

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)

    async def getScopes(
        self, wrapper: WrapperType
    ) -> Collection[api.reviewscope.ReviewScope]:
        if self.__scopes is None:
            self.__scopes = await api.reviewscope.fetchAll(
                wrapper.critic, filter=wrapper
            )
        return self.__scopes

    async def getDelegates(self, wrapper: WrapperType) -> Collection[api.user.User]:
        if self.__delegates is None:
            async with api.critic.Query[int](
                wrapper.critic,
                """SELECT uid
                     FROM repositoryfilterdelegates
                    WHERE filter={filter}""",
                filter=wrapper,
            ) as result:
                user_ids = await result.scalars()
            self.__delegates = frozenset(
                await api.user.fetchMany(wrapper.critic, user_ids)
            )
        return self.__delegates


@RepositoryFilter.cached
async def fetch(critic: api.critic.Critic, filter_id: int) -> WrapperType:
    async with RepositoryFilter.query(
        critic, ["id={filter_id}"], filter_id=filter_id
    ) as result:
        return await RepositoryFilter.makeOne(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    review: Optional[api.review.Review],
    user: Optional[api.user.User],
    file: Optional[api.file.File],
    scope: Optional[api.reviewscope.ReviewScope],
) -> Sequence[WrapperType]:
    conditions = []
    if repository or review:
        conditions.append("repository={repository}")
        if review:
            repository = await review.repository
    if user:
        conditions.append("uid={user}")
    if scope:
        conditions.append("scope={scope}")
    async with RepositoryFilter.query(
        critic, conditions, repository=repository, user=user, scope=scope
    ) as result:
        filters = await RepositoryFilter.make(critic, result)
    if review or file:
        from critic import reviewing

        evaluator = reviewing.filters.Filters()
        if review:
            evaluator.setFiles(await review.files)
        else:
            assert file is not None
            evaluator.setFiles([file])
        await evaluator.addFilters(filters)
        if not evaluator.matching_filters:
            return []
        matching_filters = set.union(*evaluator.matching_filters.values())
        return [filter for filter in filters if filter in matching_filters]
    return filters
