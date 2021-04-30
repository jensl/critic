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

from typing import Sequence, Union

from critic import api
from critic.api.transaction.setting.modify import ModifySetting
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class Settings(ResourceClass[api.setting.Setting], api_module=api.setting):
    """Settings."""

    contexts = (None, "users", "repositories", "branches", "reviews", "extensions")

    @staticmethod
    async def json(parameters: Parameters, value: api.setting.Setting) -> JSONResult:
        """Setting {
          "id": integer, // the setting's unique id
          "user": integer, // the setting's owner
          "scope": string, // the setting's scope
          "name": string, // the setting's name
          "value": any
        }"""

        if value.value_bytes is None:
            value_bytes_url = None
        else:
            value_bytes_url = f"/api/setting/{value.id}"

        return {
            "id": value.id,
            "scope": value.scope,
            "name": value.name,
            "value": value.value,
            "value_bytes_url": value_bytes_url,
            "user": value.user,
            "repository": value.repository,
            "branch": value.branch,
            "review": value.review,
            "extension": value.extension,
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.setting.Setting:
        """Retrieve one (or more) user settings of this system.

        SETTING_ID : integer

        Retrieve a user setting identified by its unique numeric id"""

        return await api.setting.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.setting.Setting, Sequence[api.setting.Setting]]:
        """Retrieve a single named user setting or multiple user settings.

        scope : SCOPE : string

        Retrieve only user settings with the given scope.

        name : NAME : string

        Retrieve only the user setting with the given name. Must be combined
        with the |scope| parameter."""

        scope = parameters.query.get("scope")
        name = parameters.query.get("name")

        user = await parameters.deduce(api.user.User)
        repository = await parameters.deduce(api.repository.Repository)
        branch = await parameters.deduce(api.branch.Branch)
        review = await parameters.deduce(api.review.Review)
        extension = await parameters.deduce(api.extension.Extension)

        if name is not None:
            if scope is None:
                raise UsageError.missingParameter("scope")
            return await api.setting.fetch(
                parameters.critic,
                scope=scope,
                name=name,
                user=user,
                repository=repository,
                branch=branch,
                review=review,
                extension=extension,
            )

        return await api.setting.fetchAll(
            parameters.critic,
            scope=scope,
            user=user,
            repository=repository,
            branch=branch,
            review=review,
            extension=extension,
        )

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.setting.Setting:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "scope": str,
                "name": str,
                "value": None,
                "user?": api.user.User,
                "repository?": api.repository.Repository,
                "branch?": api.branch.Branch,
                "review?": api.review.Review,
                "extension?": api.extension.Extension,
            },
            data,
        )

        user = await parameters.deduce(
            api.user.User, converted.get("user", critic.effective_user)
        )
        repository = await parameters.deduce(
            api.repository.Repository, converted.get("repository")
        )
        branch = await parameters.deduce(api.branch.Branch, converted.get("branch"))
        review = await parameters.deduce(api.review.Review, converted.get("review"))
        extension = await parameters.deduce(
            api.extension.Extension, converted.get("extension")
        )

        async with api.transaction.start(critic) as transaction:
            modifier = await transaction.defineSetting(
                converted["scope"],
                converted["name"],
                converted["value"],
                value_bytes=None,
                user=user,
                repository=repository,
                branch=branch,
                review=review,
                extension=extension,
            )
            return modifier.subject

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.setting.Setting],
        data: JSONInput,
    ) -> None:
        converted = await convert(parameters, {"value": None}, data)

        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                await (await transaction.modifySetting(setting)).setValue(
                    converted["value"]
                )

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[api.setting.Setting],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                await (await transaction.modifySetting(setting)).delete()
