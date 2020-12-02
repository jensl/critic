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

from critic import api
from critic import background
from critic import dbaccess
from critic import gitaccess
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject
from ..item import Insert, InsertMany, Update
from ..protocol import CreatedBranch
from . import validate_branch_name, validate_commit_set, CreateBranchUpdate


class CreateBranch(CreateAPIObject[api.branch.Branch], api_module=api.branch):
    async def create_payload(
        self, resource_name: str, branch: api.branch.Branch, /
    ) -> CreatedBranch:
        return CreatedBranch(
            resource_name, branch.id, (await branch.repository).id, branch.name
        )

    @staticmethod
    async def make(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        branch_type: api.branch.BranchType,
        name: str,
        commits: Iterable[api.commit.Commit],
        head: Optional[api.commit.Commit],
        base_branch: Optional[api.branch.Branch],
        output: Optional[str],
        is_creating_review: bool,
        pendingrefupdate_id: Optional[int],
    ) -> api.branch.Branch:
        critic = transaction.critic

        assert branch_type != "review" or base_branch is None

        await validate_branch_name(repository, name)

        commitset, head = await validate_commit_set(critic, head, commits)
        assert head

        branch = await CreateBranch(transaction).insert(
            name=name,
            repository=repository,
            head=head,
            base=base_branch,
            type=branch_type,
            size=len(commitset),
        )

        branchupdate = await CreateBranchUpdate(transaction, branch).insert(
            branch=branch,
            updater=critic.effective_user,
            to_head=head,
            to_base=base_branch,
            output=output,
        )

        if commits:
            await transaction.execute(
                InsertMany(
                    "branchcommits",
                    ["branch", "commit"],
                    (
                        dbaccess.parameters(branch=branch, commit=commit)
                        for commit in commits
                    ),
                )
            )

            await transaction.execute(
                Insert("branchupdatecommits")
                .columns("branchupdate", "commit", "associated")
                .query(
                    """
                    SELECT {branchupdate}, commit, TRUE
                      FROM branchcommits
                     WHERE branch={branch}
                    """,
                    branchupdate=branchupdate,
                    branch=branch,
                )
            )

        if pendingrefupdate_id is not None:
            if is_creating_review:
                next_state = "processed"
            else:
                next_state = "finished"

            await transaction.execute(
                Update("pendingrefupdates")
                .set(branchupdate=branchupdate, state=next_state)
                .where(id=pendingrefupdate_id)
            )

            if output:
                transaction.tables.add("pendingrefupdateoutputs")
                await transaction.execute(
                    Insert("pendingrefupdateoutputs")
                    .columns("pendingrefupdate", "output")
                    .query(
                        """
                        SELECT id, {output}
                          FROM pendingrefupdates
                         WHERE id={pendingrefupdate_id}
                        """,
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
                raise api.branch.Error(
                    f"Bad branch name: {name}", code="BAD_BRANCH_NAME"
                )

        if not background.utils.is_background_service("branchupdater"):
            transaction.pre_commit_callbacks.append(createGitBranch)

        return branch
