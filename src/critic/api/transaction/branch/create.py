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
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

from . import (
    validate_branch_name,
    validate_commit_set,
    CreatedBranch,
    CreatedBranchUpdate,
)
from .. import Query, Insert, InsertMany, Update, Transaction
from critic import api
from critic import background
from critic import gitaccess


async def create_branch(
    transaction: Transaction,
    repository: api.repository.Repository,
    branch_type: api.branch.BranchType,
    name: str,
    commits: Iterable[api.commit.Commit],
    head: Optional[api.commit.Commit],
    base_branch: Optional[api.branch.Branch],
    output: Optional[str],
    is_creating_review: bool,
    pendingrefupdate_id: Optional[int],
) -> CreatedBranch:
    critic = transaction.critic

    assert branch_type != "review" or base_branch is None

    await validate_branch_name(repository, name)

    commitset, head = await validate_commit_set(critic, head, commits)
    assert head

    created_branch = CreatedBranch(transaction, commitset, head).insert(
        name=name,
        repository=repository,
        head=head,
        base=base_branch,
        type=branch_type,
        size=len(commitset),
    )

    branchupdate = CreatedBranchUpdate(transaction, created_branch).insert(
        branch=created_branch,
        updater=critic.effective_user,
        to_head=head,
        to_base=base_branch,
        output=output,
    )

    if commits:
        transaction.items.append(
            InsertMany(
                "branchcommits",
                ["branch", "commit"],
                (dict(branch=created_branch, commit=commit) for commit in commits),
            )
        )

        transaction.tables.add("branchupdatecommits")
        transaction.items.append(
            Query(
                """INSERT
                     INTO branchupdatecommits (branchupdate, commit, associated)
                   SELECT {branchupdate}, commit, TRUE
                     FROM branchcommits
                    WHERE branch={branch}""",
                branchupdate=branchupdate,
                branch=created_branch,
            )
        )

    if pendingrefupdate_id is not None:
        if is_creating_review:
            next_state = "processed"
        else:
            next_state = "finished"

        transaction.items.append(
            Update("pendingrefupdates")
            .set(branchupdate=branchupdate, state=next_state)
            .where(id=pendingrefupdate_id)
        )

        if output:
            transaction.tables.add("pendingrefupdateoutputs")
            transaction.items.append(
                Query(
                    """INSERT
                         INTO pendingrefupdateoutputs (pendingrefupdate, output)
                       SELECT id, {output}
                         FROM pendingrefupdates
                        WHERE id={pendingrefupdate_id}""",
                    output=output,
                    pendingrefupdate_id=pendingrefupdate_id,
                )
            )

    async def createGitBranch() -> None:
        assert head
        try:
            await repository.low_level.updateref(
                "refs/heads/" + name, new_value=head.sha1, create=True
            )
        except gitaccess.GitProcessError:
            raise api.branch.Error(f"Bad branch name: {name}", code="BAD_BRANCH_NAME")

    if not background.utils.is_background_service("branchupdater"):
        transaction.pre_commit_callbacks.append(createGitBranch)

    return created_branch
