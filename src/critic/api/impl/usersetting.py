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

from typing import Tuple, Any, Optional, Set, Mapping, List

from . import apiobject
from critic import api


WrapperType = api.usersetting.UserSetting
RowType = Tuple[int, int, str, str, Any]


class UserSetting(apiobject.APIObject[WrapperType, RowType, int]):
    wrapper_class = api.usersetting.UserSetting
    column_names = ["id", "uid", "scope", "name", "value"]

    def __init__(self, args: RowType) -> None:
        (self.id, self.__user_id, self.scope, self.name, self.value) = args

    async def getUser(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__user_id)

    @staticmethod
    async def refresh(
        critic: api.critic.Critic,
        tables: Set[str],
        cached_objects: Mapping[Any, WrapperType],
    ) -> None:
        if "usersettings" not in tables:
            return

        await UserSetting.updateAll(
            critic,
            f"""SELECT {UserSetting.columns()}
                  FROM {UserSetting.table()}
                 WHERE {{id=object_ids:array}}""",
            cached_objects,
        )


@UserSetting.cached
async def fetch(
    critic: api.critic.Critic,
    usersetting_id: Optional[int],
    scope: Optional[str],
    name: Optional[str],
) -> WrapperType:
    conditions = ["uid={user}"]
    if usersetting_id is not None:
        conditions.append("id={usersetting_id}")
    else:
        conditions.extend(["scope={scope}", "name={name}"])

    async with UserSetting.query(
        critic,
        conditions,
        user=critic.effective_user,
        usersetting_id=usersetting_id,
        scope=scope,
        name=name,
    ) as result:
        try:
            return await UserSetting.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if usersetting_id is not None:
                raise api.usersetting.InvalidId(invalid_id=usersetting_id)
            assert scope is not None and name is not None
            raise api.usersetting.NotDefined(scope, name)


async def fetchAll(
    critic: api.critic.Critic, scope: Optional[str]
) -> List[WrapperType]:
    conditions = ["uid={user}"]
    if scope is not None:
        conditions.append("scope={scope}")
    async with UserSetting.query(
        critic,
        f"""SELECT {UserSetting.columns()}
              FROM {UserSetting.table()}
             WHERE {" AND ".join(conditions)}
          ORDER BY id""",
        user=critic.effective_user,
        scope=scope,
    ) as result:
        return await UserSetting.make(critic, result)
