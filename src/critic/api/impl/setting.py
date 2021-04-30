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
from typing import Callable, Tuple, Any, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api import setting as public
from .queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId


PublicType = public.Setting
ArgumentsType = Tuple[int, str, str, Any, Optional[bytes], int, int, int, int, int]


class Setting(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__scope,
            self.__name,
            self.__value,
            self.__value_bytes,
            self.__user_id,
            self.__repository_id,
            self.__branch_id,
            self.__review_id,
            self.__extension_id,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def scope(self) -> str:
        return self.__scope

    @property
    def name(self) -> str:
        return self.__name

    @property
    def value(self) -> Any:
        return self.__value

    @property
    def value_bytes(self) -> Optional[bytes]:
        return self.__value_bytes

    @property
    async def user(self) -> api.user.User:
        if self.__user_id is None:
            return None
        return await api.user.fetch(self.critic, self.__user_id)

    @property
    async def repository(self) -> api.repository.Repository:
        if self.__repository_id is None:
            return None
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    async def branch(self) -> api.branch.Branch:
        if self.__branch_id is None:
            return None
        return await api.branch.fetch(self.critic, self.__branch_id)

    @property
    async def review(self) -> api.review.Review:
        if self.__review_id is None:
            return None
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def extension(self) -> api.extension.Extension:
        if self.__extension_id is None:
            return None
        return await api.extension.fetch(self.critic, self.__extension_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "scope",
    "name",
    "value",
    "value_bytes",
    "user",
    "repository",
    "branch",
    "review",
    "extension",
)


def check_user(critic: api.critic.Critic, user: Optional[api.user.User]) -> None:
    if user:
        api.PermissionDenied.raiseUnlessUser(critic, user)
    else:
        api.PermissionDenied.raiseUnlessAdministrator(critic)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    scope: Optional[str],
    name: Optional[str],
    user: Optional[api.user.User],
    repository: Optional[api.repository.Repository],
    branch: Optional[api.branch.Branch],
    review: Optional[api.review.Review],
    extension: Optional[api.extension.Extension],
) -> PublicType:
    if setting_id is not None:
        setting = await Setting.ensureOne(
            setting_id, queries.idFetcher(critic, Setting)
        )
        check_user(critic, await setting.user)
        return setting
    assert scope and name

    check_user(critic, user)

    conditions = [
        '"scope"={scope}',
        '"name"={name}',
        '"user"={user}' if user else '"user" IS NULL',
        '"repository"={repository}' if repository else '"repository" IS NULL',
        '"branch"={branch}' if branch else '"branch" IS NULL',
        '"review"={review}' if review else '"review" IS NULL',
        '"extension"={extension}' if extension else '"extension" IS NULL',
    ]

    return Setting.storeOne(
        await queries.query(
            critic,
            *conditions,
            scope=scope,
            name=name,
            user=user,
            repository=repository,
            branch=branch,
            review=review,
            extension=extension
        ).makeOne(Setting, public.NotDefined(scope, name))
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    scope: Optional[str],
    user: Optional[api.user.User],
    repository: Optional[api.repository.Repository],
    branch: Optional[api.branch.Branch],
    review: Optional[api.review.Review],
    extension: Optional[api.extension.Extension],
) -> Sequence[PublicType]:
    check_user(critic, user)

    conditions = [
        '"scope"={scope}',
        '"user"={user}' if user else '"user" IS NULL',
        '"repository"={repository}' if repository else '"repository" IS NULL',
        '"branch"={branch}' if branch else '"branch" IS NULL',
        '"review"={review}' if review else '"review" IS NULL',
        '"extension"={extension}' if extension else '"extension" IS NULL',
    ]

    settings = await queries.query(
        critic,
        *conditions,
        scope=scope,
        user=user,
        repository=repository,
        branch=branch,
        review=review,
        extension=extension
    ).make(Setting)

    logger.debug(repr(settings))

    return Setting.store(settings)
