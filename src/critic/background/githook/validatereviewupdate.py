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
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic.gitaccess import SHA1, as_sha1

from . import ValidateError


async def validate_review_update(
    review: api.review.Review, old_sha1: SHA1, new_sha1: SHA1
) -> Optional[ValidateError]:
    critic = review.critic
    repository = await review.repository
    branch = await review.branch
    assert branch
    old_head = await branch.head

    # Sanity check: |old_sha1| must match what we think the review branch
    #               currently points at.
    if old_sha1 != old_head.sha1:
        # Bad error message, but this should really never happen.
        return ValidateError("unexpected current state")

    # Check if there's a finished branch update that has not yet been
    # processed as a review update:
    async with critic.query(
        """SELECT 1
             FROM branchupdates
  LEFT OUTER JOIN reviewupdates
                 ON (reviewupdates.branchupdate=branchupdates.id)
            WHERE branchupdates.branch={branch}
              AND reviewupdates.event IS NULL
            LIMIT 1""",
        branch=branch,
    ) as result:
        if not await result.empty():
            return ValidateError("previous update is still being processed")

    fast_forward_update = await repository.low_level.mergebase(
        old_sha1, new_sha1, is_ancestor=True
    )

    pending_rebase = await review.pending_rebase
    if pending_rebase:
        error_base = "conflicts with pending rebase: "

        # Check that the pending rebase was prepared by the user that is now
        # trying to update the review branch.
        rebaser = await pending_rebase.creator
        if rebaser != critic.effective_user:
            return ValidateError(f"{error_base} rebase prepared by {rebaser}")

        # Check that the old head isn't an ancestor of the new head.  If it is,
        # then this isn't exactly a "rebase", it's a fast-forward update.
        # What's more, it might be accepted as a rebase (even a history
        # rewrite,) with more or less confusing results.  And it's most likely
        # mistake.
        if fast_forward_update:
            return ValidateError(error_base + "update is fast-forward (not a rebase)")

        new_upstream: Optional[api.commit.Commit]
        old_upstream: Optional[api.commit.Commit]

        if isinstance(pending_rebase, api.log.rebase.MoveRebase):
            new_upstream = await pending_rebase.new_upstream
            old_upstream = await pending_rebase.old_upstream
        else:
            new_upstream = old_upstream = None

        if new_upstream:
            # Move rebase with specified new upstream: check that the pushed
            # commit is a descendant of the recorded new upstream.
            if not await repository.low_level.mergebase(
                new_upstream.sha1, new_sha1, is_ancestor=True
            ):
                return ValidateError("not a descendant of " + new_upstream.sha1[:8])
        elif old_upstream:
            # Move rebase with automatic new upstream: check that the actual new
            # upstream is not part of the review, or its set of current upstream
            # commits.
            actual_new_upstream = await repository.low_level.revparse(new_sha1 + "^")
            branch_commits = await branch.commits

            if actual_new_upstream in branch_commits:
                return ValidateError(
                    error_base
                    + "new upstream commit %s is part of the review"
                    % actual_new_upstream[:8],
                    "This rebase was prepared without specifying the new "
                    "commit onto with which the changes were rebase. The "
                    "detected new upstream commit does not make sense.",
                )

            if actual_new_upstream in await branch_commits.filtered_tails:
                return ValidateError(
                    error_base
                    + "new upstream commit %s is already an upstream commit"
                    % actual_new_upstream[:8],
                    "Rebasing the changes onto a commit that they are "
                    "already based on is not meaningful, unless you are "
                    "performing a history rewrite. If so, please cancel "
                    "the current pending rebase and prepare a history "
                    "rewrite rebase instead.",
                )
        else:
            # History rewrite: check that the pushed commit's tree is the same
            # as the current head commit's.
            new_head = await repository.low_level.fetchone(
                gitaccess.as_sha1(new_sha1), object_factory=gitaccess.GitCommit
            )
            if new_head.tree != old_head.tree:
                return ValidateError(
                    error_base + "invalid history rewrite",
                    (
                        "The difference between the old and new state of "
                        "the review branch must be empty.  Run the "
                        "command\n\n"
                        "  git diff %s..%s\n\n"
                        "to see the changes introduced."
                    )
                    % (old_sha1[:8], new_sha1[:8]),
                )
    else:
        # No rebase.  Just check that this is a fast-forward update.
        if not fast_forward_update:
            return ValidateError(
                "invalid non-fast-forward update of review branch",
                "If you are performing a rebase or history rewrite of the "
                'branch, you must use the web UI to "prepare" the rebase '
                "before pushing the update to the Git repository.",
            )

    return None
