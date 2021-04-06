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

from typing import Callable, Optional, Tuple, Sequence, Any

from critic import api, dbaccess
from critic.api import branchsetting as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult


PublicType = api.branchsetting.BranchSetting
ArgumentsType = Tuple[int, int, str, str, Any]


class BranchSetting(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__branch_id, self.__scope, self.__name, self.__value) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def branch(self) -> api.branch.Branch:
        return await api.branch.fetch(self.critic, self.__branch_id)

    @property
    def scope(self) -> str:
        return self.__scope

    @property
    def name(self) -> str:
        return self.__name

    @property
    def value(self) -> Any:
        return self.__value

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "branch", "scope", "name", "value"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    branch: Optional[api.branch.Branch],
    scope: Optional[str],
    name: Optional[str],
) -> PublicType:
    if setting_id is not None:
        return await BranchSetting.ensureOne(
            setting_id, queries.idFetcher(critic, BranchSetting), public.InvalidId
        )

    assert scope is not None and name is not None

    try:
        return BranchSetting.storeOne(
            await queries.query(critic, branch=branch, scope=scope, name=name).makeOne(
                BranchSetting
            )
        )
    except dbaccess.ZeroRowsInResult:
        raise api.branchsetting.NotDefined(scope, name)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic, branch: Optional[api.branch.Branch], scope: Optional[str]
) -> Sequence[PublicType]:
    return BranchSetting.store(
        await queries.query(critic, branch=branch, scope=scope).make(BranchSetting)
    )
