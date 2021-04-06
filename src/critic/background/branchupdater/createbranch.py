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

import logging
import textwrap
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

from .findbasebranch import find_base_branch
from critic import api
from critic import gitaccess


async def create_branch(
    critic: api.critic.Critic,
    branch_name: str,
    head: api.commit.Commit,
    *,
    commits: Optional[Iterable[gitaccess.GitCommit]] = None,
    transaction: Optional[api.transaction.Transaction] = None,
    pendingrefupdate_id: Optional[int] = None,
    is_creating_review: bool = False
) -> api.branch.Branch:
    base_branch, branch_commits = await find_base_branch(head, commits=commits)

    ncommits = len(branch_commits)
    associated_commits = "%s associated commit%s" % (
        str(ncommits) if ncommits else "no",
        "s" if ncommits != 1 else "",
    )

    if base_branch:
        url_prefixes = [api.critic.settings().system.http_prefix]
        output = textwrap.wrap(
            "Branch created based on '%s', with %s:"
            % (base_branch.name, associated_commits)
        )
        for url_prefix in url_prefixes:
            output.append(
                "  %s/log?repository=%s&branch=%s"
                % (url_prefix, head.repository.name, branch_name)
            )
        if branch_commits and not is_creating_review:
            if ncommits > 1:
                output.append("To create a review of all %d commits:" % ncommits)
            else:
                output.append("To create a review of the commit:")
            for url_prefix in url_prefixes:
                output.append(
                    "  %s/createreview?repository=%s&branch=%s"
                    % (url_prefix, head.repository.name, branch_name)
                )
    else:
        output = ["Branch created with %s." % associated_commits]

    output_string = "\n".join(output)

    async def create(
        transaction: api.transaction.Transaction,
    ) -> api.branch.Branch:
        return (
            await transaction.modifyRepository(head.repository).createBranch(
                "review" if is_creating_review else "normal",
                branch_name,
                branch_commits,
                head=head,
                base_branch=None if is_creating_review else base_branch,
                output=output_string,
                is_creating_review=is_creating_review,
                pendingrefupdate_id=pendingrefupdate_id,
            )
        ).subject

    if transaction:
        return await create(transaction)
    else:
        async with api.transaction.start(critic) as transaction:
            return await create(transaction)
