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


class BranchSettings(
    jsonapi.ResourceClass[api.branchsetting.BranchSetting], api_module=api.branchsetting
):
    """Branch settings."""

    name = "branchsettings"
    contexts = ("branches", None)
    value_class = api.branchsetting.BranchSetting

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.branchsetting.BranchSetting
    ) -> jsonapi.JSONResult:
        """BranchSetting {
             "id": integer, // the setting's unique id
             "branch": integer, // the affected branch
             "scope": string, // the setting's scope
             "name": string, // the setting's name
             "value": any
           }"""

        return {
            "id": value.id,
            "branch": value.branch,
            "scope": value.scope,
            "name": value.name,
            "value": value.value,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.branchsetting.BranchSetting:
        """Retrieve one (or more) branch settings of this system.

           SETTING_ID : integer

           Retrieve a branch setting identified by its unique numeric id"""

        return await api.branchsetting.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[
        api.branchsetting.BranchSetting, Sequence[api.branchsetting.BranchSetting]
    ]:
        """Retrieve a single named branch setting or multiple branch settings.

           scope : SCOPE : string

           Retrieve only branch settings with the given scope.

           name : NAME : string

           Retrieve only the branch setting with the given name. Must be combined
           with the |scope| parameter."""

        branch = await Branches.deduce(parameters)
        scope = parameters.getQueryParameter("scope")
        name = parameters.getQueryParameter("name")

        if name is not None:
            if not branch:
                raise jsonapi.UsageError.missingParameter("branch")
            if scope is None:
                raise jsonapi.UsageError(
                    "The 'name' parameter must be used together with the 'scope' "
                    "parameter"
                )
            return await api.branchsetting.fetch(
                parameters.critic, branch=branch, scope=scope, name=name
            )

        return await api.branchsetting.fetchAll(
            parameters.critic, branch=branch, scope=scope
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.branchsetting.BranchSetting:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters,
            {"branch?": api.branch.Branch, "scope": str, "name": str, "value": None},
            data,
        )

        branch = await Branches.deduce(parameters)

        if not branch:
            if "branch" not in converted:
                raise jsonapi.UsageError.missingInput("branch")
            branch = converted["branch"]
        elif converted.get("branch", branch) != branch:
            raise jsonapi.UsageError("Conflicting branches specified")

        assert branch

        async with api.transaction.start(critic) as transaction:
            setting = await (
                await transaction.modifyRepository(
                    await branch.repository
                ).modifyBranch(branch)
            ).defineSetting(converted["scope"], converted["name"], converted["value"])

        return await setting

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.branchsetting.BranchSetting],
        data: jsonapi.JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await jsonapi.convert(parameters, {"value": None}, data)

        async with api.transaction.start(critic) as transaction:
            for setting in values:
                branch = await setting.branch
                (
                    await transaction.modifyRepository(
                        await branch.repository
                    ).modifyBranch(branch)
                ).modifySetting(setting).setValue(converted["value"])

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.branchsetting.BranchSetting],
    ) -> None:
        critic = parameters.critic

        async with api.transaction.start(critic) as transaction:
            for setting in values:
                branch = await setting.branch
                (
                    await transaction.modifyRepository(
                        await branch.repository
                    ).modifyBranch(branch)
                ).modifySetting(setting).delete()


from .branches import Branches
