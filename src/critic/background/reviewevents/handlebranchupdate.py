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

# type: ignore

import logging

logger = logging.getLogger(__name__)

from . import ReviewMailGroup, changed_lines_per_file
from .rendercommit import render_commit
from ..replayer import extract_unmerged_paths
from critic import api


class CommitsPushedGenerator:
    email_type = "updatedReview.commitsPushed"

    def setBranchUpdate(self, branchupdate):
        self.branchupdate = branchupdate

    def setChangesets(self, changesets):
        self.changesets = changesets

    async def __call__(self, mail):
        review = await mail.group.event.review
        from_user = mail.group.from_user
        to_user = mail.to_user

        commits = await self.branchupdate.associated_commits
        if len(commits) == 1:
            what = "an additional commit"
        else:
            what = "%d additional commits" % len(commits)

        branch = await review.branch
        repository = await review.repository

        mail.add_section(
            f"{from_user.fullname} has updated the review by pushing {what} to "
            "the branch",
            f"  {branch.name}",
            "in the repository",
            *(f"  {url}" for url in await repository.urls),
        )

        if to_user in await review.assigned_reviewers:
            rfcs = set()
            for changeset in self.changesets:
                rfcs.update(
                    await api.reviewablefilechange.fetchAll(
                        review, changeset=changeset, assignee=to_user
                    )
                )
            if rfcs:
                mail.add_section(
                    "These changes were assigned to you:",
                    *await changed_lines_per_file(mail, rfcs),
                )

        for commit in commits.topo_ordered:
            mail.add_section(
                *await render_commit(mail.group, commit, 3), wrap_lines=False
            )


class ReviewRebasedGenerator:
    email_type = "updatedReview.reviewRebased"

    def setRebase(self, rebase):
        self.rebase = rebase

    async def __call__(self, mail):
        review = await mail.group.event.review
        from_user = mail.group.from_user

        if isinstance(self.rebase, api.rebase.HistoryRewrite):
            mail.add_section(
                f"{from_user.fullname} has rewritten the history on the review "
                "branch."
            )
        else:
            mail.add_section(
                f"{from_user.fullname} has rebased the changes on the review "
                f"branch onto a new upstream."
            )

            replay = await self.rebase.equivalent_merge
            if not replay:
                replay = await self.rebase.replayed_rebase

            unmerged_paths = extract_unmerged_paths(replay) if replay else None
            if unmerged_paths:
                mail.add_section(
                    "Conflicts were detected in these paths:",
                    "",
                    *("  " + path for path in unmerged_paths),
                )

        branch = await review.branch
        commits = await branch.commits

        branch_log = [
            f"{commit.sha1[:8]} {commit.summary}" for commit in commits.topo_ordered
        ]

        mail.add_section(
            "The new branch log is:", "", *("  " + line for line in branch_log)
        )


async def handle_branchupdate(critic, event):
    branchupdate = await event.branchupdate
    review = await event.review

    if review.state == "draft":
        return

    rebase = await branchupdate.rebase

    if rebase is None:
        generator = CommitsPushedGenerator()
        generator.setBranchUpdate(branchupdate)
        generator.setChangesets(
            await api.changeset.fetchMany(critic, branchupdate=branchupdate)
        )
    else:
        generator = ReviewRebasedGenerator()
        generator.setRebase(rebase)

    group = ReviewMailGroup(event, await event.user, generator.email_type)

    async with group:
        await group.ensure_parent_message_ids()
        await group.generate(generator)
