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

from typing import Sequence, Optional, Union

from critic import api
from critic import jsonapi


async def modify(
    transaction: api.transaction.Transaction, setting: api.usersetting.UserSetting
) -> api.transaction.usersetting.ModifyUserSetting:
    return await transaction.modifyUser(await setting.user).modifyUserSetting(setting)


class UserSettings(
    jsonapi.ResourceClass[api.usersetting.UserSetting], api_module=api.usersetting
):
    """The (current user's) user settings."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.usersetting.UserSetting
    ) -> jsonapi.JSONResult:
        """UserSetting {
             "id": integer, // the setting's unique id
             "user": integer, // the setting's owner
             "scope": string, // the setting's scope
             "name": string, // the setting's name
             "value": any
           }"""

        return {
            "id": value.id,
            "user": value.user,
            "scope": value.scope,
            "name": value.name,
            "value": value.value,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.usersetting.UserSetting:
        """Retrieve one (or more) user settings of this system.

           USERSETTING_ID : integer

           Retrieve a user setting identified by its unique numeric id"""

        return await api.usersetting.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.usersetting.UserSetting, Sequence[api.usersetting.UserSetting]]:
        """Retrieve a single named user setting or multiple user settings.

           scope : SCOPE : string

           Retrieve only user settings with the given scope.

           name : NAME : string

           Retrieve only the user setting with the given name. Must be combined
           with the |scope| parameter."""

        scope = parameters.getQueryParameter("scope")
        name = parameters.getQueryParameter("name")

        if name is not None:
            if scope is None:
                raise jsonapi.UsageError.missingParameter("scope")
            return await api.usersetting.fetch(
                parameters.critic, scope=scope, name=name
            )

        return await api.usersetting.fetchAll(parameters.critic, scope=scope)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.usersetting.UserSetting:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {"user?": api.user.User, "scope": str, "name": str, "value": None},
            data,
        )
        user = converted.get("user", critic.effective_user)

        async with api.transaction.Transaction(critic) as transaction:
            modifier = await transaction.modifyUser(user).defineSetting(
                converted["scope"], converted["name"], converted["value"],
            )

        return await modifier

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.usersetting.UserSetting],
        data: jsonapi.JSONInput,
    ) -> None:
        converted = await jsonapi.convert(parameters, {"value": None}, data)

        async with api.transaction.Transaction(parameters.critic) as transaction:
            for setting in values:
                (await modify(transaction, setting)).setValue(converted["value"])

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.usersetting.UserSetting],
    ) -> None:
        async with api.transaction.Transaction(parameters.critic) as transaction:
            for setting in values:
                (await modify(transaction, setting)).delete()
