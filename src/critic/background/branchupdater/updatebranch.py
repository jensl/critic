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
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

from .findbasebranch import find_base_branch
from critic import api


async def update_branch(
    branch: api.branch.Branch,
    from_commit: api.commit.Commit,
    to_commit: api.commit.Commit,
    *,
    is_updating_review: bool = False,
    pendingrefupdate_id: Optional[int] = None,
    output: Optional[List[str]] = None,
    perform_update: bool = False,
    force_associate: Optional[Iterable[api.commit.Commit]] = None,
) -> api.branchupdate.BranchUpdate:
    critic = branch.critic
    repository = await branch.repository
    base_branch = await branch.base_branch

    if base_branch or branch.type == "review":
        # For branches with a base branch, and review branches, fetch
        # `branch.commits` and use that to limit what commits are added to the
        # branch.
        current_commits = await branch.commits

        logger.debug("current_commits=%r", current_commits)
        logger.debug("from_commit=%r", from_commit)
        logger.debug("to_commit=%r", to_commit)

        if await from_commit.isAncestorOf(to_commit):
            # Fast-forward update.
            associated_commits = await api.commitset.calculateFromBranchUpdate(
                critic,
                current_commits,
                from_commit,
                to_commit,
                force_include=force_associate,
            )
            disassociated_commits = api.commitset.empty(critic)
        else:
            mergebase = await repository.mergeBase(from_commit, to_commit)

            new_commits: Optional[api.commitset.CommitSet]
            if mergebase in current_commits:
                kept_commits = current_commits.getAncestorsOf(
                    mergebase, include_self=True
                )
                added_commits = await api.commitset.calculateFromBranchUpdate(
                    critic, kept_commits, mergebase, to_commit
                )
                new_commits = await kept_commits.union(added_commits)
            else:
                new_base_branch, new_commits = await find_base_branch(
                    to_commit, exclude_branches=[branch]
                )
                if base_branch is not None:
                    # Only change the base branch if one was recorded previously.
                    base_branch = new_base_branch

            associated_commits = new_commits - current_commits
            disassociated_commits = current_commits - new_commits
    else:
        # For branches without a base branch, e.g. `master` in a typical
        # repository, we just use a `git rev-list` based approach, which is far
        # faster. Baseless branches should simply "contain" all reachable
        # commits, so no fancy limitation is required. And also, accessing
        # `branch.commits` is potentially very expensive, since it likely
        # contains very many commits.
        associated_commits = await api.commit.fetchRange(
            from_commit=from_commit, to_commit=to_commit
        )
        disassociated_commits = await api.commit.fetchRange(
            from_commit=to_commit, to_commit=from_commit
        )

    if output is None:
        output = []
    if associated_commits:
        output.append(
            "Associated %d new commit%s to the branch."
            % (len(associated_commits), "s" if len(associated_commits) > 1 else "")
        )
    if disassociated_commits:
        output.append(
            "Disassociated %d old commit%s from the branch."
            % (
                len(disassociated_commits),
                "s" if len(disassociated_commits) > 1 else "",
            )
        )
    output_string = "\n".join(output)

    async def do_update_branch() -> None:
        await repository.low_level.updateref(
            branch.ref, old_value=from_commit.sha1, new_value=to_commit.sha1
        )

    async with api.transaction.start(critic) as transaction:
        branch_modifier = await transaction.modifyRepository(repository).modifyBranch(
            branch
        )
        branchupdate = await branch_modifier.recordUpdate(
            to_commit,
            base_branch,
            associated_commits,
            disassociated_commits,
            output=output_string,
            pendingrefupdate_id=pendingrefupdate_id,
        )

        if perform_update:
            transaction.post_commit_callbacks.append(do_update_branch)

    return branchupdate
