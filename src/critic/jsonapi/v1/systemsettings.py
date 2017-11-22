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

from typing import Sequence, Optional, Union

from critic import api
from critic import jsonapi


class SystemSettings(
    jsonapi.ResourceClass[api.systemsetting.SystemSetting], api_module=api.systemsetting
):
    """The system settings."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.systemsetting.SystemSetting
    ) -> jsonapi.JSONResult:
        """SystemSetting {
             "id": number, // the setting's id
             "key": string, // the setting's key
             "description": string, // the setting's description
             "value": any, // the setting's value
           }"""

        return {
            "id": value.id,
            "key": value.key,
            "description": value.description,
            "value": value.value,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.systemsetting.SystemSetting:
        """Retrieve one (or more) system settings.

           SETTING_ID : string

           Retrieve a system setting identified by its unique id."""

        return await api.systemsetting.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[
        api.systemsetting.SystemSetting, Sequence[api.systemsetting.SystemSetting]
    ]:
        """Retrieve all system settings.

           prefix : PREFIapi.systemsetting.SystemSetting : string

           Return only settings whose id has the specified prefix. Setting ids
           are always a sequence of full stop-separated identifiers (at least
           two, and thus at least one full stop.) The prefix should be the first
           such identifier, or a sequence of them separated by full stops. There
           should be no trailing flul stop in the prefix."""

        key_parameter = parameters.getQueryParameter("key")
        if key_parameter is not None:
            return await api.systemsetting.fetch(parameters.critic, key=key_parameter)

        prefix_parameter = parameters.getQueryParameter("prefix")
        return await api.systemsetting.fetchAll(
            parameters.critic, prefix=prefix_parameter
        )

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.systemsetting.SystemSetting],
        data: jsonapi.JSONInput,
    ) -> None:
        if not isinstance(values, jsonapi.SingleValue):
            raise jsonapi.UsageError("Updating multiple system settings not supported")

        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters, {"value": jsonapi.check.TypeChecker()}, data
        )

        async with api.transaction.start(critic) as transaction:
            transaction.modifySystemSetting(values.get()).setValue(converted["value"])

    @staticmethod
    async def update_many(
        parameters: jsonapi.Parameters, data: Sequence[jsonapi.JSONInput]
    ) -> None:
        critic = parameters.critic

        settings = []
        values = {}
        for item in data:
            converted = await jsonapi.convert(
                parameters, {"id": int, "value?": jsonapi.check.TypeChecker()}, item
            )
            setting = await api.systemsetting.fetch(critic, converted["id"])
            settings.append(setting)
            if "value" in converted:
                values[setting] = converted["value"]

        if values:
            async with api.transaction.start(critic) as transaction:
                for setting, value in values.items():
                    transaction.modifySystemSetting(setting).setValue(value)
