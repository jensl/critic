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

import logging
from typing import Sequence, Optional, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class TrackedBranches(
    jsonapi.ResourceClass[api.trackedbranch.TrackedBranch], api_module=api.trackedbranch
):
    """The Git repositories on this system."""

    contexts = (None, "repositories", "reviews")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.trackedbranch.TrackedBranch
    ) -> jsonapi.JSONResult:
        """TrackedBranch {
             "id": integer, // the repository's id
             "disabled": boolean, /// true if the tracking is disabled
             "name": string, // the branch name in the local repository
             "repository": integer, // the repository
             "branch": integer or null, // the local branch,
             "source": {
               "url": string, // remote repository URL
               "name": string, // the branch name in the remote repository
             }
           }"""

        source = value.source

        return {
            "id": value.id,
            "disabled": value.is_disabled,
            "name": value.name,
            "repository": value.repository,
            "branch": value.branch,
            "source": {"url": source.url, "name": source.name},
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.trackedbranch.TrackedBranch:
        """Retrieve one (or more) tracked branches in this system.

           TRACKEDBRANCH_ID : integer

           Retrieve a tracked branch identified by its unique numeric id."""

        return await api.trackedbranch.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[
        api.trackedbranch.TrackedBranch, Sequence[api.trackedbranch.TrackedBranch]
    ]:
        branch = await Branches.deduce(parameters)
        if not branch:
            review = await Reviews.deduce(parameters)
            if review:
                branch = await review.branch
        if branch:
            return await api.trackedbranch.fetch(parameters.critic, branch=branch)

        repository = await Repositories.deduce(parameters)

        name_argument = parameters.getQueryParameter("name")
        if name_argument:
            if not repository:
                raise jsonapi.UsageError(
                    "Named branch access must have repository specified."
                )
            return await api.trackedbranch.fetch(
                parameters.critic, repository=repository, name=name_argument
            )

        return await api.trackedbranch.fetchAll(
            parameters.critic, repository=repository
        )


from .branches import Branches
from .repositories import Repositories
from .reviews import Reviews
