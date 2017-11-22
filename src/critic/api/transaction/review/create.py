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
from typing import Iterable, Optional, Union

logger = logging.getLogger(__name__)

from . import CreatedReview, CreatedReviewEvent
from .. import Transaction, Query, Insert, InsertMany
from ..branch import validate_commit_set

from critic import api


async def create_review(
    transaction: Transaction,
    repository: api.repository.Repository,
    owners: Iterable[api.user.User],
    head: Optional[api.commit.Commit],
    commits: Optional[Iterable[api.commit.Commit]],
    branch: Optional[Union[api.branch.Branch, CreatedBranch]],
    target_branch: Optional[api.branch.Branch],
    via_push: bool,
) -> CreatedReview:
    critic = transaction.critic

    if branch:
        commits = await branch.commits
        head = await branch.head
    else:
        assert commits is not None
        commits, head = await validate_commit_set(critic, head, commits)

    commits_behind: Optional[int]
    if target_branch:
        try:
            tracked_branch = await api.trackedbranch.fetch(
                transaction.critic, branch=target_branch
            )
        except api.trackedbranch.NotFound:
            pass
        else:
            raise api.review.Error(
                f"Invalid target branch: {target_branch.name} tracks "
                f"{tracked_branch.source.name} in {tracked_branch.source.url}"
            ) from None
        upstreams = await commits.filtered_tails
        if len(upstreams) != 1:
            raise api.review.Error("Branch has multiple upstream commits")
        (upstream,) = upstreams
        if not await upstream.isAncestorOf(await target_branch.head):
            raise api.review.Error("Branch is not based on target branch")
        commits_behind = await repository.low_level.revlist(
            include=[(await target_branch.head).sha1], exclude=[head.sha1], count=True
        )
    else:
        commits_behind = None

    summary: Optional[str]
    if len(commits) == 1:
        (commit,) = commits
        summary = commit.summary
    else:
        summary = None

    review = CreatedReview(transaction, branch, commits).insert(
        repository=repository,
        summary=summary,
        branch=branch,
        integration_target=target_branch,
        integration_behind=commits_behind,
    )

    event = CreatedReviewEvent.ensure(transaction, review, "created")

    transaction.items.append(
        InsertMany(
            "reviewusers",
            ["review", "uid", "owner"],
            (dict(review=review, uid=owner, owner=True) for owner in owners),
        )
    )

    if branch:
        transaction.tables.add("reviewcommits")
        if not via_push:
            transaction.items.append(
                Query(
                    """INSERT
                         INTO reviewcommits (review, commit)
                       SELECT {review}, commit
                         FROM branchcommits
                        WHERE branch={branch}""",
                    review=review,
                    branch=branch,
                )
            )

            transaction.tables.add("reviewupdates")
            transaction.items.append(
                Query(
                    """INSERT
                         INTO reviewupdates (branchupdate, event)
                       SELECT id, {event}
                         FROM branchupdates
                        WHERE branch={branch}""",
                    event=event,
                    branch=branch,
                )
            )
    else:
        transaction.items.append(
            InsertMany(
                "reviewcommits",
                ["review", "commit"],
                (dict(review=review, commit=commit) for commit in commits),
            )
        )

        async def protectCommit() -> None:
            assert head
            await repository.protectCommit(head)

        transaction.pre_commit_callbacks.append(protectCommit)

    transaction.wakeup_service("reviewupdater")

    return review


from ..branch import CreatedBranch
