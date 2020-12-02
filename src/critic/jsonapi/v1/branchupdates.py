# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from typing import Sequence, Awaitable, Collection

from critic import api
from ..exceptions import PathError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import numeric_id
from .timestamp import timestamp


class BranchUpdates(
    ResourceClass[api.branchupdate.BranchUpdate], api_module=api.branchupdate
):
    """Branch updates in the Git repositories."""

    contexts = (None, "branches", "reviews")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.branchupdate.BranchUpdate
    ) -> JSONResult:
        """BranchUpdate {
          "id": integer, // the branch update's id
          "branch": integer, // the updated branch's id
          "updater": integer, // the id of the user that caused the update
          "from_head": integer, // the id of the branch's head before the
                                // update
          "to_head": integer, // the id of the branch's head after the update
          "associated": [integer], // the id of each newly associated commit
          "disassociated": [integer], // the id of each newly disassociated
                                      // commit
          "timestamp": float,
          "output": string, // Git hook output
        }"""

        async def topo_ordered(
            commitset: Awaitable[api.commitset.CommitSet],
        ) -> Collection[api.commit.Commit]:
            return list((await commitset).topo_ordered)

        return {
            "id": value.id,
            "branch": value.branch,
            "updater": value.updater,
            "from_head": await value.from_head,
            "to_head": await value.to_head,
            "associated": topo_ordered(value.associated_commits),
            "disassociated": topo_ordered(value.disassociated_commits),
            "timestamp": timestamp(value.timestamp),
            "output": value.output,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.branchupdate.BranchUpdate:
        """Retrieve one (or more) branch updates.

        BRANCHUPDATE_ID : integer

        Retrieve a branch update identified by its unique numeric id."""

        branchupdate = await api.branchupdate.fetch(
            parameters.critic, numeric_id(argument)
        )
        branch = await parameters.deduce(api.branch.Branch)

        if branch and branch != branchupdate.branch:
            raise PathError("Branch update is not of the specified branch")

        return branchupdate

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.branchupdate.BranchUpdate]:
        """Retrieve all updates of a particular branch.

        branch : BRANCH_ID : integer

        The branch whose updates to retrieve, identified by the branch's
        unique numeric id."""

        branch = await parameters.deduce(api.branch.Branch)
        updater = await parameters.deduce(api.user.User)

        return await api.branchupdate.fetchAll(
            parameters.critic, branch=branch, updater=updater
        )

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.branchupdate.BranchUpdate:
        return await api.branchupdate.fetch(parameters.critic, numeric_id(value))


from .branches import Branches
from .users import Users
