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
from typing import Collection, Optional

logger = logging.getLogger(__name__)

from .ensurechangesets import ensure_changesets
from .processrebase import RebaseProcessingFailure, process_rebase
from ..githook import emit_output, set_pendingrefupdate_state
from critic import api


async def process_review_branch_update(
    review: api.review.Review,
    branchupdate: api.branchupdate.BranchUpdate,
    pendingrefupdate_id: int,
) -> None:
    critic = review.critic

    associated_commits = await branchupdate.associated_commits
    disassociated_commits = await branchupdate.disassociated_commits

    rebase = await review.pending_rebase

    added_commits: Optional[api.commitset.CommitSet] = None
    if rebase:
        try:
            rebase_processing_result = await process_rebase(
                review, branchupdate, pendingrefupdate_id
            )
        except RebaseProcessingFailure:
            # Set state to 'finished' rather than to 'failed', since it's
            # partially performed already, and setting to 'failed' causes a
            # partial revert of the update. Implementing a full revert would
            # be another option, but is more work and more complexity.
            await set_pendingrefupdate_state(
                critic, pendingrefupdate_id, "processed", "finished"
            )
            return
        added_changesets = rebase_processing_result.changesets
    else:
        assert associated_commits
        assert not disassociated_commits
        added_commits = associated_commits
        added_changesets = ()

    if added_commits:
        output = "Adding %d commit%s to the review ..." % (
            len(added_commits),
            "s" if len(added_commits) != 1 else "",
        )
        await emit_output(critic, pendingrefupdate_id, output)

        # Ensure that changesets are processed for each individual added commit.
        added_changesets = await ensure_changesets(review, added_commits)

    assigned_reviewers_before = await review.assigned_reviewers

    async with api.transaction.start(critic) as transaction:
        modifier = transaction.modifyReview(review)
        await modifier.recordBranchUpdate(branchupdate)

        if rebase:
            modifier.finishRebase(
                rebase,
                branchupdate,
                new_upstream=rebase_processing_result.new_upstream,
                equivalent_merge=rebase_processing_result.equivalent_merge,
                replayed_rebase=rebase_processing_result.replayed_rebase,
            )

        if added_commits:
            await modifier.addCommits(branchupdate, added_commits)

        if added_changesets:
            await modifier.addChangesets(added_changesets, branchupdate=branchupdate)

    if added_commits:
        await emit_output(critic, pendingrefupdate_id, "  done.")

    assigned_reviewers = await review.assigned_reviewers - assigned_reviewers_before
    if assigned_reviewers:
        lines = ["Assigned reviewers:"]
        lines.extend(sorted("  " + str(reviewer) for reviewer in assigned_reviewers))
        await emit_output(critic, pendingrefupdate_id, "\n".join(lines))

    updater = await branchupdate.updater

    addressed_issues = [
        issue
        for issue in await api.comment.fetchAll(
            critic, review=review, addressed_by=branchupdate
        )
        # Don't mention changes to other users' unpublished comments.
        if not issue.is_draft or await issue.author == updater
    ]
    if addressed_issues:
        lines = ["Addressed issues:"]
        for issue in addressed_issues:
            text, _, _ = issue.text.partition("\n")
            lines.extend(
                [
                    "  Issue raised by %s" % await issue.author,
                    '    "%s"' % textwrap.shorten(text, 70),
                ]
            )
        await emit_output(critic, pendingrefupdate_id, "\n".join(lines))

    await set_pendingrefupdate_state(
        critic, pendingrefupdate_id, "processed", "finished"
    )
