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

import logging

logger = logging.getLogger(__name__)

from critic import api
from ...background.githook import emit_output


async def delete_branch(
    branch: api.branch.Branch, pendingrefupdate_id: int = None
) -> None:
    critic = branch.critic
    output = "Deleted branch with %d associated commits." % branch.size

    async with api.transaction.start(critic) as transaction:
        branch_modifier = await transaction.modifyRepository(
            await branch.repository
        ).modifyBranch(branch)
        await branch_modifier.deleteBranch(pendingrefupdate_id=pendingrefupdate_id)

    await emit_output(critic, pendingrefupdate_id, output)
