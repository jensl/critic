# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
from typing import (
    Awaitable,
    Collection,
    List,
    Optional,
    Sequence,
    TypedDict,
    Union,
)

from critic.base.types import BooleanWithReason

logger = logging.getLogger(__name__)

from critic import api
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..types import JSONInput, JSONResult
from ..utils import many, numeric_id, sorted_by_id
from ..values import Values
from ..valuewrapper import ValueWrapper
from .timestamp import timestamp


class ChangeCount(TypedDict):
    commit: int
    total_changes: int
    reviewed_changes: int


class Partition(TypedDict):
    commits: Collection[api.commit.Commit]
    rebase: Optional[api.rebase.Rebase]


class Progress(TypedDict):
    reviewing: float
    open_issues: int


async def change_counts_as_dict(value: api.review.Review) -> Collection[ChangeCount]:
    change_counts = await value.progress_per_commit
    return [
        {
            "commit": change_count.commit_id,
            "total_changes": change_count.total_changes,
            "reviewed_changes": change_count.reviewed_changes,
        }
        for change_count in change_counts
    ]


async def partitions(value: api.review.Review) -> Collection[Partition]:
    result: List[Partition] = []

    def add_partition(partition: api.partition.Partition) -> None:
        if partition is None:
            return

        partition_rebase = partition.following.rebase if partition.following else None

        result.append(
            {
                "commits": list(partition.commits.topo_ordered),
                "rebase": partition_rebase,
            }
        )

        if partition.following:
            add_partition(partition.following.partition)

    add_partition(await value.first_partition)
    return result


async def changesets(
    value: api.review.Review,
) -> Optional[ValueWrapper[Sequence[api.changeset.Changeset]]]:
    changesets = await value.changesets
    if changesets is None:
        return None
    return await sorted_by_id(changesets.values())


async def filters(
    value: api.review.Review,
) -> ValueWrapper[Sequence[api.reviewfilter.ReviewFilter]]:
    return await sorted_by_id(value.filters)


async def progress(value: api.review.Review) -> Progress:
    progress = await value.progress
    return {
        "reviewing": progress.reviewing,
        "open_issues": progress.open_issues,
    }


class Integration(TypedDict):
    target_branch: api.branch.Branch
    commits_behind: Optional[int]
    state: api.review.IntegrationState
    squashed: bool
    autosquashed: bool
    strategy_used: Optional[api.review.IntegrationStrategy]
    conflicts: Awaitable[ValueWrapper[Sequence[api.file.File]]]
    error_message: Optional[str]


async def integration(review: api.review.Review) -> Optional[Integration]:
    value = await review.integration
    if value is None:
        return None
    return Integration(
        target_branch=value.target_branch,
        commits_behind=value.commits_behind,
        state=value.state,
        squashed=value.squashed,
        autosquashed=value.autosquashed,
        strategy_used=value.strategy_used,
        conflicts=sorted_by_id(value.conflicts),
        error_message=value.error_message,
    )


class Reviews(
    ResourceClass[api.review.Review],
    api_module=api.review,
    exceptions=(api.review.Error, api.repository.Error, api.branch.Error),
):
    """The reviews in this system."""

    @staticmethod
    async def json(parameters: Parameters, value: api.review.Review) -> JSONResult:
        """Review {
          "id": integer,
          "state": string,
          "summary": string,
          "description": string or null,
          "repository": integer,
          "branch": integer,
          "owners": integer[],
          "active_reviewers": integer[],
          "assigned_reviewers": integer[],
          "watchers": integer[],
          "partitions": Partition[],
          "changesets": integer[],
          "issues": integer[],
          "notes": integer[],
          "pending_update": integer or null,
          "pending_rebase": integer or null,
          "progress": Progress,
          "progress_per_commit": CommitChangeCount[],
          "filters": integer[],
        }

        Partition {
          "commits": integer[],
          "rebase": integer or null,
        }

        Progress {
          "reviewing": float, // Ratio of reviewed / total changed lines.
          "issues": integer,  // Number of open issues.
        }

        CommitChangeCount {
          "commit_id": integer,
          "total_changes": integer,
          "reviewed_changes": integer,
        }"""

        if "changesets" in parameters.include:
            # Prefetch all commits in the review, which will speed up processing
            # of changesets later.
            await value.prefetchCommits()

            if "reviewablefilechanges" in parameters.include:
                # Prefetch all reviewable file changes for the review, which
                # greatly optimizes later looking them up per review.
                await api.reviewablefilechange.fetchAll(value)

        async def can_publish() -> bool:
            return bool(await value.can_publish)

        async def can_close() -> bool:
            return bool(await value.can_close)

        async def can_drop() -> bool:
            return bool(await value.can_drop)

        async def can_reopen() -> bool:
            return bool(await value.can_reopen)

        return {
            "id": value.id,
            "state": value.state,
            "can_publish": can_publish(),
            "can_close": can_close(),
            "can_drop": can_drop(),
            "can_reopen": can_reopen(),
            "is_accepted": value.is_accepted,
            "summary": value.summary,
            "description": value.description,
            "repository": value.repository,
            "branch": value.branch,
            "owners": sorted_by_id(value.owners),
            "active_reviewers": sorted_by_id(value.active_reviewers),
            "assigned_reviewers": sorted_by_id(value.assigned_reviewers),
            "watchers": sorted_by_id(value.watchers),
            "partitions": partitions(value),
            "changesets": changesets(value),
            "issues": sorted_by_id(value.issues),
            "notes": sorted_by_id(value.notes),
            "pending_update": value.pending_update,
            "pending_rebase": value.pending_rebase,
            "progress": progress(value),
            "progress_per_commit": change_counts_as_dict(value),
            "filters": filters(value),
            "tags": sorted_by_id(value.tags),
            "last_changed": timestamp(value.last_changed),
            "pings": sorted_by_id(value.pings),
            "integration": integration(value),
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.review.Review:
        """Retrieve one (or more) reviews in this system.

        REVIEW_ID : integer

        Retrieve a review identified by its unique numeric id."""

        return await api.review.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.review.Review, Sequence[api.review.Review]]:
        """Retrieve all reviews in this system.

        branch : BRANCH : -

        Retrieve only the review associated with the specified branch.

        repository : REPOSITORY : -

        Include only reviews in one repository, identified by the
        repository's unique numeric id or short-name.

        state : STATE[,STATE,...] : -

        Include only reviews in the specified state.  Valid values are:
        <code>open</code>, <code>closed</code>, <code>dropped</code>.

        category : CATEGORY : "incoming", "outgoing" or "other"

        Include only reviews in the specified category for the currently
        signed in user. All categories mean the user is associated with the
        review somehow; "incoming" means the user is an assigned reviewer,
        "outgoing" means the user is an owner, and "other" is any other
        review with which the user is associated.

        A given review can be included in both the "incoming" and "outgoing"
        categories. Closed or dropped reviews are not included in any
        category. Unpublished reviews are only included in the "outgoing"
        category (assuming the current user owns the unpublished review.)"""

        branch = await parameters.deduce(api.branch.Branch)
        if branch:
            return await api.review.fetch(parameters.critic, branch=branch)

        repository = await parameters.deduce(api.repository.Repository)
        state = parameters.query.get("state", converter=many(api.review.as_state))
        category = parameters.query.get("category", converter=api.review.as_category)

        return await api.review.fetchAll(
            parameters.critic, repository=repository, state=state, category=category
        )

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.review.Review:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "repository!": api.repository.Repository,
                "owners?": [api.user.User],
                "branch?": str,
                "commits": [api.commit.Commit],
                "summary?": str,
                "description?": str,
                "integration?": {"target_branch": api.branch.Branch},
            },
            data,
        )

        owners = converted.get("owners", [critic.effective_user])
        commits = converted["commits"]
        integration = converted.get("integration")
        target_branch = integration["target_branch"] if integration else None

        if "branch" in converted:
            try:
                await api.branch.fetch(
                    critic, repository=converted["repository"], name=converted["branch"]
                )
            except api.branch.InvalidName:
                pass
            else:
                raise UsageError.invalidInput(
                    data, "branch", details="the branch already exists"
                )

        async with api.transaction.start(critic) as transaction:
            created_branch: Optional[api.branch.Branch]
            if "branch" in converted:
                created_branch = (
                    await transaction.modifyRepository(
                        converted["repository"]
                    ).createBranch("review", converted["branch"], commits)
                ).subject
                commits = None
            else:
                created_branch = None

            review_modifier = await transaction.createReview(
                converted["repository"],
                owners,
                commits=commits,
                branch=created_branch,
                target_branch=target_branch,
            )

            if "summary" in converted:
                await review_modifier.setSummary(converted["summary"])
            if "description" in converted:
                await review_modifier.setSummary(converted["description"])

            return review_modifier.subject

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.review.Review],
        data: JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "state?": api.review.STATE_VALUES,
                "summary?": str,
                "description?": str,
                "branch?": str,
                "owners?": [api.user.User],
                "integration?": {"target_branch": api.branch.Branch},
            },
            data,
        )

        if "branch" in converted:
            if len(values) > 1:
                raise UsageError("Will not update branch of multiple reviews")

        async with api.transaction.start(critic) as transaction:
            for review in values:
                modifier = transaction.modifyReview(review)

                if "summary" in converted:
                    await modifier.setSummary(converted["summary"])

                if "description" in converted:
                    await modifier.setDescription(converted["description"])

                if "branch" in converted:
                    if await review.branch is None:
                        logger.debug("commits: %r", await review.commits)

                        branch = (
                            await transaction.modifyRepository(
                                await review.repository
                            ).createBranch(
                                "review",
                                converted["branch"],
                                await review.commits,
                            )
                        ).subject

                        await modifier.setBranch(branch)
                    else:
                        branch_modifier = await modifier.modifyBranch()
                        await branch_modifier.setName(converted["branch"])

                if "owners" in converted:
                    await modifier.setOwners(converted["owners"])

                if "integration" in converted:
                    await modifier.setTargetBranch(
                        converted["integration"]["target_branch"]
                    )

                # Do this last, so that any mails generated are done so using
                # up-to-date information, in case we're setting other things in
                # the same transaction.

                if "state" in converted:
                    new_state = converted["state"]
                    if new_state == "open":
                        if review.state == "draft":
                            await modifier.publishReview()
                        elif review.state != "open":
                            await modifier.reopenReview()
                    elif review.state == "open":
                        if new_state == "dropped":
                            await modifier.dropReview()
                        elif review.is_accepted and new_state == "closed":
                            await modifier.closeReview()

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.review.Review]
    ) -> None:
        critic = parameters.critic

        async with api.transaction.start(critic) as transaction:
            for review in values:
                await transaction.modifyReview(review).deleteReview()

    @classmethod
    async def deduce(cls, parameters: Parameters) -> Optional[api.review.Review]:
        review = parameters.in_context(api.review.Review)
        review_parameter = parameters.query.get("review")
        if review_parameter is not None:
            if review is not None:
                raise UsageError(
                    "Redundant query parameter: review=%s" % review_parameter
                )
            review = await api.review.fetch(
                parameters.critic, numeric_id(review_parameter)
            )
        return review

    @classmethod
    async def setAsContext(
        cls, parameters: Parameters, review: api.review.Review, /
    ) -> None:
        await super().setAsContext(parameters, review)

        # Also set the review's repository and branch as context.
        await Repositories.setAsContext(parameters, await review.repository)
        branch = await review.branch
        if branch:
            await Branches.setAsContext(parameters, branch)

        # Finally, include the current user's unpublished batch in the result.
        await includeUnpublished(parameters, review)


from .batches import includeUnpublished
from .branches import Branches
from .repositories import Repositories
