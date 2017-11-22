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

import json
from typing import Tuple, Any, Iterable, Sequence, Optional, Set, Mapping

from critic import api
from critic import dbaccess

from . import apiobject

WrapperType = api.systemsetting.SystemSetting
ArgumentsType = Tuple[int, str, str, Any, bool]


class SystemSetting(apiobject.APIObject[WrapperType, ArgumentsType, str]):
    wrapper_class = WrapperType
    column_names = ["id", "key", "description", "value", "privileged"]

    def __init__(self, args: ArgumentsType) -> None:
        (self.id, self.key, self.description, self.value, self.is_privileged) = args

    def wrap(self, critic: api.critic.Critic) -> WrapperType:
        if self.is_privileged:
            api.PermissionDenied.raiseUnlessSystem(critic)
        return super().wrap(critic)


@SystemSetting.cached
async def fetch(
    critic: api.critic.Critic, setting_id: Optional[int], key: Optional[str]
) -> WrapperType:
    if setting_id is not None:
        condition = "id={setting_id}"
    else:
        condition = "key={key}"
    async with SystemSetting.query(
        critic, [condition], setting_id=setting_id, key=key
    ) as result:
        try:
            return await SystemSetting.makeOne(critic, result)
        except dbaccess.ZeroRowsInResult:
            assert key is not None
            raise api.systemsetting.InvalidKey(value=key)


@SystemSetting.cachedMany
async def fetchMany(
    critic: api.critic.Critic, setting_ids: Iterable[int], keys: Iterable[str],
) -> Sequence[WrapperType]:
    if setting_ids is not None:
        condition = "id=ANY({setting_ids})"
        setting_ids = list(setting_ids)
    else:
        condition = "key=ANY({keys})"
        keys = list(keys)
    async with SystemSetting.query(
        critic, [condition], setting_ids=setting_ids, keys=keys
    ) as result:
        return await SystemSetting.make(critic, result)


async def fetchAll(
    critic: api.critic.Critic, prefix: Optional[str]
) -> Sequence[WrapperType]:
    try:
        async with critic.query("SELECT 1 FROM systemsettings WHERE FALSE") as result:
            await result.ignore()
    except dbaccess.ProgrammingError:
        # The |systemsettings| table doesn't exist. This happens during upgrade
        # from a pre-2.0 system. Ignore the error here. Any code that actually
        # depends on specific settings will crash instead.
        return []

    try:
        api.PermissionDenied.raiseUnlessSystem(critic)
    except api.PermissionDenied:
        include_privileged = False
    else:
        include_privileged = True

    conditions = ["(NOT privileged OR {include_privileged})"]

    if prefix is not None:
        if "%" in prefix:
            raise api.systemsetting.InvalidPrefix(prefix)
        conditions.append("key LIKE {prefix}")
        prefix += ".%"

    async with SystemSetting.query(
        critic, conditions, prefix=prefix, include_privileged=include_privileged
    ) as result:
        return await SystemSetting.make(critic, result)
