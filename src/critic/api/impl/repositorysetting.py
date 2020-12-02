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

from typing import Tuple, Optional, Sequence, Any

from . import apiobject
from critic import api
from critic.api import repositorysetting as public

WrapperType = api.repositorysetting.RepositorySetting
ArgumentsType = Tuple[int, int, str, str, Any]


class RepositorySetting(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.repositorysetting.RepositorySetting
    column_names = ["id", "repository", "scope", "name", "value"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.__repository_id, self.scope, self.name, self.value) = args

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)


@public.fetchImpl
@RepositorySetting.cached
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    repository: Optional[api.repository.Repository],
    scope: Optional[str],
    name: Optional[str],
) -> WrapperType:
    conditions = []
    if setting_id is not None:
        conditions.append("id={setting_id}")
    else:
        conditions.extend(["repository={repository}", "scope={scope}", "name={name}"])

    async with RepositorySetting.query(
        critic,
        conditions,
        setting_id=setting_id,
        repository=repository,
        scope=scope,
        name=name,
    ) as result:
        try:
            return await RepositorySetting.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if scope is not None and name is not None:
                raise api.repositorysetting.NotDefined(scope, name)
            raise


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    scope: Optional[str],
) -> Sequence[WrapperType]:
    conditions = []
    if repository is not None:
        conditions.append("repository={repository}")
    if scope is not None:
        conditions.append("scope={scope}")
    async with RepositorySetting.query(
        critic, conditions, repository=repository, scope=scope
    ) as result:
        return await RepositorySetting.make(critic, result)
