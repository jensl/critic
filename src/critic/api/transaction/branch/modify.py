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

import itertools
import logging
from typing import Optional, Iterable

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from critic import dbaccess
from critic.gitaccess import GitError
from ..base import TransactionBase
from ..branchsetting.mixin import ModifyBranch as BranchSettingMixin
from ..item import (
    Insert,
    InsertMany,
    Delete,
    Update,
    Verify,
)
from ..modifier import Modifier
from . import validate_branch_name, CreateBranchUpdate
from .create import CreateBranch


class ModifyBranch(BranchSettingMixin, Modifier[api.branch.Branch]):
    def __init__(
        self,
        transaction: TransactionBase,
        branch: api.branch.Branch,
    ):
        super().__init__(transaction, branch)
        # transaction.lock("branches", id=branch.id)

    async def setName(self, new_name: str) -> None:
        branch = self.subject

        old_name = branch.name
        repository = await branch.repository

        # Check that the new name is valid, ignoring whether it conflicts with
        # the old ref, since that ref will be deleted.
        await validate_branch_name(repository, new_name, ignore_conflict=old_name)

        await self.transaction.execute(Update(branch).set(name=new_name))

        async def renameGitBranch() -> None:
            head = await branch.head
            await repository.low_level.updateref(
                f"refs/heads/{old_name}", old_value=head.sha1, delete=True
            )
            try:
                await repository.low_level.updateref(
                    f"refs/heads/{new_name}", new_value=head.sha1, create=True
                )
            except GitError:
                # Try to recover from a failure to create the new ref by
                # protecting the now (possibly) unreferenced commits.
                await repository.protectCommit(head)
                raise

        self.transaction.post_commit_callbacks.append(renameGitBranch)

    async def recordUpdate(
        self,
        head: api.commit.Commit,
        base_branch: Optional[api.branch.Branch],
        associated_commits: api.commitset.CommitSet,
        disassociated_commits: api.commitset.CommitSet,
        *,
        output: Optional[str] = None,
        pendingrefupdate_id: Optional[int] = None,
        previous_head: Optional[api.commit.Commit] = None,
    ) -> api.branchupdate.BranchUpdate:
        branch = self.subject
        transaction = self.transaction
        critic = transaction.critic

        assert branch.type == "normal" or base_branch is None

        logger.debug("head=%r", head)
        logger.debug("associated_commits=%r", associated_commits)
        logger.debug("disassociated_commits=%r", disassociated_commits)

        repository = await branch.repository

        size_delta = len(associated_commits) - len(disassociated_commits)

        current_head = await branch.head
        if previous_head is not None and previous_head != current_head:
            raise api.branch.Error("branch head modified concurrently")

        logger.debug("current_head=%r", current_head)

        if associated_commits:
            logger.debug("associated_commits.tails=%r", associated_commits.tails)
            if len(associated_commits.heads) != 1:
                raise api.branch.Error("invalid associated commits set: multiple heads")
            if (
                not disassociated_commits
                and current_head not in associated_commits.tails
            ):
                raise api.branch.Error(
                    "invalid associated commits set: current head is not a tail"
                )

        if branch.is_merged:
            # The branch is currently flagged as merged. Check if the new head
            # commit is associated with another branch already, and if not,
            # clear this branch's "merged" flag.
            async with critic.query(
                """SELECT TRUE
                     FROM branches
                     JOIN branchcommits ON (branch=branches.id)
                    WHERE id!={branch}
                      AND repository={repository}
                      AND commit={head}""",
                branch=branch,
                repository=repository,
                head=head,
            ) as result:
                is_merged = await result.empty()
        else:
            # An update of branch X will never cause it to be flagged as merged.
            #
            # Non-ff updates can represent arbitrary state changes, so in theory
            # such an update could plausibly lead to a state where the branch
            # could be said to be merged, but we ignore that.
            is_merged = False

        await transaction.execute(
            Verify("branches").that(head=current_head).where(id=branch.id)
        )

        await transaction.execute(
            Update(branch).set(
                head=head,
                base=base_branch,
                merged=is_merged,
                size=branch.size + size_delta,
            )
        )

        branchupdate = await CreateBranchUpdate(transaction, branch).insert(
            branch=branch,
            updater=critic.effective_user,
            from_head=await branch.head,
            to_head=head,
            from_base=await branch.base_branch,
            to_base=base_branch,
            output=output,
        )

        if associated_commits:
            await transaction.execute(
                InsertMany(
                    "branchcommits",
                    ["branch", "commit"],
                    (
                        dbaccess.parameters(branch=branch, commit=commit)
                        for commit in associated_commits
                    ),
                )
            )
        if disassociated_commits:
            await transaction.execute(
                Delete("branchcommits").where(
                    branch=branch, commit=list(disassociated_commits)
                )
            )

        await transaction.execute(
            InsertMany(
                "branchupdatecommits",
                ["branchupdate", "commit", "associated"],
                (
                    [
                        dict(
                            branchupdate=branchupdate,
                            commit=commit,
                            associated=associated,
                        )
                        for commit, associated in itertools.chain(
                            zip(associated_commits, itertools.repeat(True)),
                            zip(disassociated_commits, itertools.repeat(False)),
                        )
                    ]
                ),
            )
        )

        if pendingrefupdate_id is not None:
            if branch.type == "review":
                # The reviewupdater service will perform additional tasks before
                # we're done.
                next_state = "processed"
            else:
                next_state = "finished"

            await transaction.execute(
                Update("pendingrefupdates")
                .set(branchupdate=branchupdate, state=next_state)
                .where(id=pendingrefupdate_id)
            )

            if next_state == "finished" and output:
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

        transaction.tables.add("branchmerges")
        await transaction.execute(
            Insert("branchmerges")
            .columns("branch", "branchupdate")
            .query(
                """
                SELECT id, {branchupdate}
                  FROM branches
                 WHERE id!={branch}
                   AND repository={repository}
                   AND base IS NOT NULL
                   AND head=ANY({associated_commits})
                """,
                branchupdate=branchupdate,
                branch=branch,
                repository=repository,
                associated_commits=[*associated_commits],
            )
        )
        await transaction.execute(
            Update("branches")
            .set(merged=True)
            .where(
                """
                id IN (
                    SELECT branch
                      FROM branchmerges
                     WHERE branchupdate={branchupdate}
                )
                """,
                branchupdate=branchupdate,
            )
        )

        return branchupdate

    async def revertUpdate(self, branchupdate: api.branchupdate.BranchUpdate) -> None:
        raise Exception("NOT IMPLEMENTED")

    async def archive(self) -> None:
        raise Exception("NOT IMPLEMENTED")

    async def deleteBranch(self, *, pendingrefupdate_id: Optional[int] = None) -> None:
        await super().delete()

        branch = self.subject

        repository = await branch.repository
        head = await branch.head

        if pendingrefupdate_id is not None:
            next_state = "finished"

            self.transaction.tables.add("pendingrefupdates")
            await self.transaction.execute(
                Update("pendingrefupdates")
                .set(state=next_state)
                .where(id=pendingrefupdate_id)
            )

        async def deleteGitBranch() -> None:
            await repository.low_level.updateref(
                f"refs/heads/{branch.name}", old_value=head.sha1, delete=True
            )

        if not background.utils.is_background_service("branchupdater"):
            # Do this post commit to ensure we don't do it and then fail to
            # actually commit the transaction. Leaving the branch in the
            # repository only is considered a better option than leaving it in
            # the database only.
            self.transaction.post_commit_callbacks.append(deleteGitBranch)

    # Branch settings
    # ===============

    @staticmethod
    async def create(
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
    ) -> ModifyBranch:
        return ModifyBranch(
            transaction,
            await CreateBranch.make(
                transaction,
                repository,
                branch_type,
                name,
                commits,
                head,
                base_branch,
                output,
                is_creating_review,
                pendingrefupdate_id,
            ),
        )
