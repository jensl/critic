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

from typing import Optional, Tuple, Sequence, Any

from . import apiobject
from critic import api


WrapperType = api.branchsetting.BranchSetting
ArgumentsType = Tuple[int, int, str, str, Any]


class BranchSetting(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = ["id", "branch", "scope", "name", "value"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.__branch_id, self.scope, self.name, self.value) = args

    async def getBranch(self, critic: api.critic.Critic) -> api.branch.Branch:
        return await api.branch.fetch(critic, self.__branch_id)


@BranchSetting.cached
async def fetch(
    critic: api.critic.Critic,
    setting_id: Optional[int],
    branch: Optional[api.branch.Branch],
    scope: Optional[str],
    name: Optional[str],
) -> WrapperType:
    conditions = []
    if setting_id is not None:
        conditions.append("id={setting_id}")
    else:
        conditions.extend(["branch={branch}", "scope={scope}", "name={name}"])

    async with BranchSetting.query(
        critic,
        conditions,
        setting_id=setting_id,
        branch=branch,
        scope=scope,
        name=name,
    ) as result:
        try:
            return await BranchSetting.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if setting_id is not None:
                raise api.branchsetting.InvalidId(invalid_id=setting_id)
            assert scope is not None and name is not None
            raise api.branchsetting.NotDefined(scope, name)


async def fetchAll(
    critic: api.critic.Critic, branch: Optional[api.branch.Branch], scope: Optional[str]
) -> Sequence[WrapperType]:
    conditions = ["TRUE"]
    if branch is not None:
        conditions.append("branch={branch}")
    if scope is not None:
        conditions.append("scope={scope}")
    async with BranchSetting.query(
        critic, conditions, branch=branch, scope=scope
    ) as result:
        return await BranchSetting.make(critic, result)
