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
from critic import dbaccess
from . import CreateReviewEvent, commits_behind_target_branch
from ..item import InsertMany
from ..base import TransactionBase
from ..branch import validate_commit_set
from ..createapiobject import CreateAPIObject
from ..item import Insert


class CreateReview(CreateAPIObject[api.review.Review], api_module=api.review):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        owners: Iterable[api.user.User],
        head: Optional[api.commit.Commit],
        commits: Optional[Iterable[api.commit.Commit]],
        branch: Optional[api.branch.Branch],
        target_branch: Optional[api.branch.Branch],
        via_push: bool,
    ) -> api.review.Review:
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
            commits_behind = await commits_behind_target_branch(
                repository, head, target_branch, commits
            )
        else:
            commits_behind = None

        summary: Optional[str]
        if len(commits) == 1:
            (commit,) = commits
            summary = commit.summary
        else:
            summary = None

        review = await CreateReview(transaction).insert(
            repository=repository,
            summary=summary,
            branch=branch,
            integration_target=target_branch,
            integration_behind=commits_behind,
        )

        event = await CreateReviewEvent.ensure(transaction, review, "created")

        await transaction.execute(
            InsertMany(
                "reviewusers",
                ["review", "event", "uid", "owner"],
                (
                    dbaccess.parameters(
                        review=review, event=event, uid=owner, owner=True
                    )
                    for owner in owners
                ),
            )
        )

        if branch:
            if not via_push:
                await transaction.execute(
                    Insert("reviewcommits")
                    .columns("review", "commit")
                    .query(
                        """
                        SELECT {review}, commit
                          FROM branchcommits
                         WHERE branch={branch}
                        """,
                        review=review,
                        branch=branch,
                    )
                )

                await transaction.execute(
                    Insert("reviewupdates")
                    .columns("branchupdate", "event")
                    .query(
                        """
                        SELECT id, {event}
                          FROM branchupdates
                         WHERE branch={branch}
                        """,
                        event=event,
                        branch=branch,
                    )
                )
        else:
            await transaction.execute(
                InsertMany(
                    "reviewcommits",
                    ["review", "commit"],
                    (
                        dbaccess.parameters(review=review, commit=commit)
                        for commit in commits
                    ),
                )
            )

            async def protectCommit() -> None:
                assert head
                await repository.protectCommit(head)

            transaction.pre_commit_callbacks.append(protectCommit)

        transaction.wakeup_service("reviewupdater")

        return review
