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

import contextlib
import logging
import time
from typing import Sequence, Optional, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class Branches(
    jsonapi.ResourceClass[api.branch.Branch],
    api_module=api.branch,
    exceptions=(api.branch.Error, api.repository.Error),
):
    """Branches in the Git repositories."""

    contexts = (None, "repositories")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.branch.Branch
    ) -> jsonapi.JSONResult:
        """Branch {
          "id": integer, // the branch's id
          "type": "normal" or "review", // the branch's type
          "name": string, // the branch's name
          "repository": integer, // the branch's repository's id
          "base_branch": integer, // the branch's base branch
          "head": integer, // the branch's head commit's id
          "size": integer, // number of commits associated with the branch
          "updates": integer[]
        }"""

        return {
            "id": value.id,
            "type": value.type,
            "name": value.name,
            "is_archived": value.is_archived,
            "is_merged": value.is_merged,
            "repository": value.repository,
            "base_branch": value.base_branch,
            "head": value.head,
            "size": value.size,
            "updates": value.updates,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.branch.Branch:
        """Retrieve one (or more) branches in the Git repositories.

        BRANCH_ID : integer

        Retrieve a branch identified by its unique numeric id."""

        return await api.branch.fetch(parameters.critic, jsonapi.numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.branch.Branch, Sequence[api.branch.Branch]]:
        """Retrieve all branches in the Git repositories.

        repository : REPOSITORY : -

        Include only branches in one repository, identified by the
        repository's unique numeric id or short-name.

        name : NAME : string

        Retrieve only the branch with the specified name. The name should
        <em>not</em> include the "refs/heads/" prefix. When this parameter
        is specified a repository must be specified as well, either in the
        resource path or using the <code>repository</code> parameter. Other
        filtering parameters are ignored.

        created_by : USER : -

        Retrieve branches created by the specified user, ordered by creation
        date with the most recently created branch first. Can not be combined
        with `updated_by`.

        updated_by : USER : -

        Retrieve branches updated by the specified user, ordered by update
        date with the most recently updated branch first. Can not be combined
        with `created_by`."""

        repository = await Repositories.deduce(parameters)
        name_parameter = parameters.getQueryParameter("name")
        if name_parameter:
            if repository is None:
                raise jsonapi.UsageError(
                    "Named branch access must have repository specified."
                )
            return await api.branch.fetch(
                parameters.critic, repository=repository, name=name_parameter
            )
        created_by = await Users.fromParameter(parameters, "created_by")
        updated_by = await Users.fromParameter(parameters, "updated_by")
        if created_by is not None and updated_by is not None:
            raise jsonapi.UsageError("Both `created_by` and `updated_by` used.")
        exclude_reviewed_branches = (
            parameters.getQueryParameter("exclude_reviewed_branches") == "yes"
        )
        order_by = parameters.getQueryParameter(
            "order_by", "name", converter=api.branch.as_order
        )
        return await api.branch.fetchAll(
            parameters.critic,
            repository=repository,
            created_by=created_by,
            updated_by=updated_by,
            exclude_reviewed_branches=exclude_reviewed_branches,
            order=order_by,
        )

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.branch.Branch]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for branch in values:
                await (
                    await transaction.modifyRepository(
                        await branch.repository
                    ).modifyBranch(branch)
                ).deleteBranch()

    @staticmethod
    async def deduce(parameters: jsonapi.Parameters) -> Optional[api.branch.Branch]:
        branch = parameters.context.get("branches")
        branch_parameter = parameters.getQueryParameter("branch")
        if branch_parameter is not None:
            if branch is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: branch=%s" % branch_parameter
                )
            branch_id, name = jsonapi.id_or_name(branch_parameter)
            if branch_id is not None:
                branch = await api.branch.fetch(parameters.critic, branch_id)
            else:
                repository = await Repositories.deduce(parameters)
                if repository is None:
                    raise jsonapi.UsageError(
                        "Named branch access must have repository specified."
                    )
                branch = await api.branch.fetch(
                    parameters.critic, repository=repository, name=name
                )

        return branch

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, branch: api.branch.Branch
    ) -> None:
        parameters.setContext(Branches.name, branch)


from .repositories import Repositories
from .users import Users
