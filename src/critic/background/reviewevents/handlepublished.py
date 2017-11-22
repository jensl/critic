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

from . import ReviewMailGroup, changed_lines_per_file, indented
from .rendercommit import render_commit
from critic import api


async def generate(mail):
    review = await mail.group.event.review
    from_user = mail.group.from_user
    to_user = mail.to_user

    if mail.type == "newishReview":
        mail.add_section(
            "Note: This review was published some time ago. This message was "
            'sent to you in place of the regular "New Review" message that '
            "was sent out when the review was published, since at that time "
            "you were not associated with the review, and thus not a recipient "
            "of that message."
        )
        mail.add_separator()

    branch = await review.branch
    repository = await review.repository

    mail.add_section(
        f"{from_user.fullname} has requested a review of the changes on " "the branch",
        f"  {branch.name}",
        "in the repository",
        *indented(2, *await repository.urls),
    )

    reviewers_and_watchers = []
    assigned_reviewers = await review.assigned_reviewers
    if assigned_reviewers:
        reviewers_and_watchers.extend(
            ["The following reviewers are assigned to review the changes:"]
            + [f"  {reviewer}" for reviewer in assigned_reviewers]
        )
    else:
        reviewers_and_watchers.append("No-one is assigned to review the changes.")
    watchers = await review.watchers
    if watchers:
        reviewers_and_watchers.extend(
            ["", "These additional users are following the review:"]
            + [f"  {watcher}" for watcher in watchers]
        )
    mail.add_section(*reviewers_and_watchers)

    if to_user in assigned_reviewers:
        rfcs = await api.reviewablefilechange.fetchAll(review, assignee=to_user)
        mail.add_section(
            "These changes were assigned to you:",
            *await changed_lines_per_file(mail, rfcs),
        )

    if mail.type == "newReview":
        # Non-published reviews can not be rebased. (And even if that was
        # supported, the rebase should probably be done as a rewrite of the set
        # of commits in the review, rather than recording the rebase as such.)
        assert not await review.rebases

    # Use the set of commits associated with the branch. For brand new reviews,
    # there's no different set of commits we could use, since, as checked above,
    # reviews can't be rebased until after they have been published. For other
    # reviews, if |mail.type == "newishReview"|, this is probably more useful
    # than any other set, that might include commits from different versions
    # of the branch, and many old, already squashed, fixups.
    commits = await branch.commits

    if mail.group.event.type == "branchupdate":
        branchupdate = await mail.group.event.branchupdate

        # Reverse the effect of the branch update, so that this mail represents
        # the state immediately before it. Recipients will also receive a mail
        # about the update, which will make less sense if the information in
        # this mail already reflects the post-update state.
        commits = await (commits - await branchupdate.associated_commits).union(
            await branchupdate.disassociated_commits
        )

    for commit in commits.topo_ordered:
        mail.add_section(*await render_commit(mail.group, commit, 3), wrap_lines=False)


async def handle_published(critic, event):
    group = ReviewMailGroup(event, await event.user, "newReview")

    async with group:
        await group.generate(generate, add_review_message_ids=True)
