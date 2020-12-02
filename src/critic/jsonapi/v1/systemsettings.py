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

from typing import Sequence, Union

from critic import api
from ..check import anything, convert, input_spec, optional
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class SystemSettings(
    ResourceClass[api.systemsetting.SystemSetting], api_module=api.systemsetting
):
    """The system settings."""

    @staticmethod
    async def json(
        parameters: Parameters, value: api.systemsetting.SystemSetting
    ) -> JSONResult:
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

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.systemsetting.SystemSetting:
        """Retrieve one (or more) system settings.

        SETTING_ID : string

        Retrieve a system setting identified by its unique id."""

        return await api.systemsetting.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
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

        key_parameter = parameters.query.get("key")
        if key_parameter is not None:
            return await api.systemsetting.fetch(parameters.critic, key=key_parameter)

        prefix_parameter = parameters.query.get("prefix")
        return await api.systemsetting.fetchAll(
            parameters.critic, prefix=prefix_parameter
        )

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.systemsetting.SystemSetting],
        data: JSONInput,
    ) -> None:
        if not values.is_single:
            raise UsageError("Updating multiple system settings not supported")

        critic = parameters.critic

        converted = await convert(parameters, input_spec(value=anything()), data)

        async with api.transaction.start(critic) as transaction:
            await transaction.modifySystemSetting(values.get()).setValue(
                converted["value"]
            )

    @staticmethod
    async def update_many(
        parameters: Parameters, data: Sequence[JSONInput]
    ) -> Sequence[api.systemsetting.SystemSetting]:
        critic = parameters.critic

        settings = []
        values = {}
        for item in data:
            converted = await convert(
                parameters, input_spec(id=int, value=optional(anything())), item
            )
            setting = await api.systemsetting.fetch(critic, converted["id"])
            settings.append(setting)
            if "value" in converted:
                values[setting] = converted["value"]

        if values:
            async with api.transaction.start(critic) as transaction:
                for setting, value in values.items():
                    await transaction.modifySystemSetting(setting).setValue(value)

        return settings
