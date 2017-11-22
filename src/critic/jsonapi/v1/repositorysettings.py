# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

RepositorySetting = api.repositorysetting.RepositorySetting


class RepositorySettings(
    jsonapi.ResourceClass[RepositorySetting], api_module=api.repositorysetting
):
    """Repository settings."""

    contexts = (None, "repositories")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: RepositorySetting
    ) -> jsonapi.JSONResult:
        """RepositorySetting {
             "id": integer, // the setting's unique id
             "repository": integer, // the affected repository
             "scope": string, // the setting's scope
             "name": string, // the setting's name
             "value": any
           }"""

        return {
            "id": value.id,
            "repository": value.repository,
            "scope": value.scope,
            "name": value.name,
            "value": value.value,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> RepositorySetting:
        """Retrieve one (or more) repository settings of this system.

           SETTING_ID : integer

           Retrieve a repository setting identified by its unique numeric id"""

        return await api.repositorysetting.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[RepositorySetting, Sequence[RepositorySetting]]:
        """Retrieve a single named repository setting or multiple repository settings.

           scope : SCOPE : string

           Retrieve only repository settings with the given scope.

           name : NAME : string

           Retrieve only the repository setting with the given name. Must be combined
           with the |scope| parameter."""

        repository = await Repositories.deduce(parameters)
        scope = parameters.getQueryParameter("scope")
        name = parameters.getQueryParameter("name")

        if name is not None:
            if not repository:
                raise jsonapi.UsageError.missingParameter("repository")
            if scope is None:
                raise jsonapi.UsageError(
                    "The 'name' parameter must be used together with the 'scope' "
                    "parameter"
                )
            return await api.repositorysetting.fetch(
                parameters.critic, repository=repository, scope=scope, name=name
            )

        return await api.repositorysetting.fetchAll(
            parameters.critic, repository=repository, scope=scope
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> RepositorySetting:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {
                "repository?": api.repository.Repository,
                "scope": str,
                "name": str,
                "value": None,
            },
            data,
        )

        repository = await Repositories.deduce(parameters)

        if not repository:
            if "repository" not in converted:
                raise jsonapi.UsageError.missingInput("repository")
            repository = converted["repository"]
        elif converted.get("repository", repository) != repository:
            raise jsonapi.UsageError("Conflicting repositories specified")
        assert repository

        async with api.transaction.start(critic) as transaction:
            modifier = await transaction.modifyRepository(repository).defineSetting(
                converted["scope"], converted["name"], converted["value"],
            )

        return await modifier

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[RepositorySetting],
        data: jsonapi.JSONInput,
    ) -> None:
        converted = await jsonapi.convert(parameters, {"value": None}, data)

        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                transaction.modifyRepository(await setting.repository).modifySetting(
                    setting
                ).setValue(converted["value"])

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[RepositorySetting]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                transaction.modifyRepository(await setting.repository).modifySetting(
                    setting
                ).delete()


from .repositories import Repositories
