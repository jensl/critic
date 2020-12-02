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

from typing import Sequence, Union

from critic import api
from critic.api.transaction.repositorysetting.modify import ModifyRepositorySetting
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values

RepositorySetting = api.repositorysetting.RepositorySetting


async def modify(
    transaction: api.transaction.Transaction,
    setting: api.repositorysetting.RepositorySetting,
) -> ModifyRepositorySetting:
    return transaction.modifyRepository(await setting.repository).modifySetting(setting)


class RepositorySettings(
    ResourceClass[RepositorySetting], api_module=api.repositorysetting
):
    """Repository settings."""

    contexts = (None, "repositories")

    @staticmethod
    async def json(parameters: Parameters, value: RepositorySetting) -> JSONResult:
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

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> RepositorySetting:
        """Retrieve one (or more) repository settings of this system.

        SETTING_ID : integer

        Retrieve a repository setting identified by its unique numeric id"""

        return await api.repositorysetting.fetch(
            parameters.critic, numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[RepositorySetting, Sequence[RepositorySetting]]:
        """Retrieve a single named repository setting or multiple repository settings.

        scope : SCOPE : string

        Retrieve only repository settings with the given scope.

        name : NAME : string

        Retrieve only the repository setting with the given name. Must be combined
        with the |scope| parameter."""

        repository = await parameters.deduce(api.repository.Repository)
        scope = parameters.query.get("scope")
        name = parameters.query.get("name")

        if name is not None:
            if not repository:
                raise UsageError.missingParameter("repository")
            if scope is None:
                raise UsageError(
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
    async def create(parameters: Parameters, data: JSONInput) -> RepositorySetting:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "repository?": api.repository.Repository,
                "scope": str,
                "name": str,
                "value": None,
            },
            data,
        )

        repository = await parameters.deduce(api.repository.Repository)

        if not repository:
            if "repository" not in converted:
                raise UsageError.missingInput("repository")
            repository = converted["repository"]
        elif converted.get("repository", repository) != repository:
            raise UsageError("Conflicting repositories specified")
        assert repository

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.modifyRepository(repository).defineSetting(
                    converted["scope"],
                    converted["name"],
                    converted["value"],
                )
            ).subject

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[RepositorySetting],
        data: JSONInput,
    ) -> None:
        converted = await convert(parameters, {"value": None}, data)

        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                await (await modify(transaction, setting)).setValue(converted["value"])

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[RepositorySetting]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for setting in values:
                await (await modify(transaction, setting)).delete()
