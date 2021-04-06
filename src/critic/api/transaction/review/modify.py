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
from typing import (
    Collection,
    Container,
    Dict,
    Iterable,
    Optional,
    overload,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from ..base import TransactionBase
from ..item import Insert, InsertMany, FetchScalars, Delete
from ..modifier import Modifier
from ..comment.mixin import ModifyReview as CommentMixin
from ..rebase.mixin import ModifyReview as RebaseMixin
from ..reviewfilter.mixin import ModifyReview as ReviewFilterMixin
from ..reviewintegrationrequest.mixin import (
    ModifyReview as ReviewIntegrationRequestMixin,
)
from ..branch.modify import ModifyBranch
from . import (
    CreateReviewEvent,
    ReviewUser,
    commits_behind_target_branch,
    raiseUnlessPublished,
)
from .create import CreateReview
from .updatereviewtags import UpdateReviewTags


class ModifyReview(
    CommentMixin,
    RebaseMixin,
    ReviewFilterMixin,
    ReviewIntegrationRequestMixin,
    Modifier[api.review.Review],
):
    def __init__(
        self,
        transaction: TransactionBase,
        review: api.review.Review,
    ) -> None:
        super().__init__(transaction, review)
        # transaction.lock("reviews", id=self.subject.id)

    def _updateReviewTags(self) -> None:
        self.transaction.finalizers.add(UpdateReviewTags(self.subject))

    async def _clearReviewTags(self) -> None:
        await self.transaction.execute(
            Delete("reviewusertags").where(review=self.subject)
        )

    async def _setState(
        self, state: api.review.State, event: api.reviewevent.EventType
    ) -> None:
        async with self.update(state=state) as update:
            update.set(state=state)
        await CreateReviewEvent.ensure(self.transaction, self.subject, event)

    async def publishReview(self) -> None:
        api.review.Error.raiseUnless(await (await self.subject.refresh()).can_publish)
        await self._setState("open", "published")

    async def closeReview(self) -> None:
        api.review.Error.raiseUnless(await (await self.subject.refresh()).can_close)
        await self._setState("closed", "closed")
        await self._clearReviewTags()

    async def dropReview(self) -> None:
        api.review.Error.raiseUnless(await (await self.subject.refresh()).can_drop)
        await self._setState("dropped", "dropped")
        await self._clearReviewTags()

    async def reopenReview(self) -> None:
        api.review.Error.raiseUnless(await (await self.subject.refresh()).can_reopen)
        await self._setState("open", "reopened")
        self._updateReviewTags()

    async def setSummary(self, new_summary: str) -> None:
        async with self.update(summary=new_summary) as update:
            update.set(summary=new_summary)

    async def setDescription(self, new_description: str) -> None:
        async with self.update(description=new_description) as update:
            update.set(description=new_description)

    async def setOwners(self, new_owners: Iterable[api.user.User]) -> None:
        new_owners = set(new_owners)
        current_owners = await self.subject.owners

        added_owners = set(new_owners).difference(current_owners)
        removed_owners = set(current_owners).difference(new_owners)

        for user in added_owners:
            ReviewUser.ensure(self.transaction, self.subject, user, is_owner=True)
        for user in removed_owners:
            ReviewUser.ensure(self.transaction, self.subject, user, is_owner=False)

    async def setBranch(self, branch: api.branch.Branch) -> ModifyBranch:
        if await (await self.reload()).branch is not None:
            raise api.review.Error("Review already has a branch set")

        async with self.update(branch=branch.id) as update:
            update.set(branch=branch)

        branchupdate_ids = await self.transaction.execute(
            FetchScalars[int]("branchupdates", "id").where(branch=branch)
        )
        branchupdate_events: Dict[int, api.reviewevent.ReviewEvent] = {}
        system = api.user.system(self.critic)

        for branchupdate_id in branchupdate_ids:
            branchupdate_events[branchupdate_id] = await CreateReviewEvent.create(
                self.transaction, self.subject, "branchupdate", user=system
            )

        await self.transaction.execute(
            InsertMany(
                "reviewupdates",
                ["branchupdate", "event"],
                (
                    dbaccess.parameters(
                        branchupdate=branchupdate_id,
                        event=branchupdate_events[branchupdate_id],
                    )
                    for branchupdate_id in branchupdate_ids
                ),
            )
        )

        return ModifyBranch(self.transaction, branch)

    async def modifyBranch(self) -> ModifyBranch:
        branch = await self.subject.branch
        if branch is None:
            raise api.review.Error("Review has no branch")
        return ModifyBranch(self.transaction, branch)

    async def submitChanges(
        self,
        batch: api.batch.Batch,
        batch_comment: Optional[api.comment.Comment] = None,
    ) -> api.batch.Batch:
        raiseUnlessPublished(self.subject)
        return await submit_changes(
            self.transaction, self.subject, batch, batch_comment
        )

    async def discardChanges(self, discard: Container[api.batch.DiscardValue]) -> None:
        raiseUnlessPublished(self.subject)
        await discard_changes(self.transaction, self.subject, discard)

    async def markChangeAsReviewed(
        self, rfc: api.reviewablefilechange.ReviewableFileChange
    ) -> None:
        assert self.subject == await rfc.review
        raiseUnlessPublished(self.subject)
        await mark_change_as_reviewed(self.transaction, rfc)

    async def markChangeAsPending(
        self, rfc: api.reviewablefilechange.ReviewableFileChange
    ) -> None:
        assert self.subject == await rfc.review
        raiseUnlessPublished(self.subject)
        await mark_change_as_pending(self.transaction, rfc)

    async def recordBranchUpdate(
        self, branchupdate: api.branchupdate.BranchUpdate
    ) -> api.reviewevent.ReviewEvent:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        event = await CreateReviewEvent.ensure(
            self.transaction,
            self.subject,
            "branchupdate",
            user=await branchupdate.updater,
        )

        await self.transaction.execute(
            Insert("reviewupdates").values(branchupdate=branchupdate, event=event)
        )

        return event

    async def addCommits(
        self,
        branchupdate: api.branchupdate.BranchUpdate,
        commits: Iterable[api.commit.Commit],
    ) -> None:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        await self.transaction.execute(
            InsertMany(
                "reviewcommits",
                ["review", "branchupdate", "commit"],
                (
                    dbaccess.parameters(
                        review=self.subject, branchupdate=branchupdate, commit=commit
                    )
                    for commit in commits
                ),
            )
        )

    @overload
    async def addChangesets(
        self,
        event: api.reviewevent.ReviewEvent,
        changesets: Collection[api.changeset.Changeset],
        *,
        branchupdate: api.branchupdate.BranchUpdate,
    ) -> None:
        ...

    @overload
    async def addChangesets(
        self,
        event: api.reviewevent.ReviewEvent,
        changesets: Collection[api.changeset.Changeset],
        *,
        commits: api.commitset.CommitSet,
    ) -> None:
        ...

    async def addChangesets(
        self,
        event: api.reviewevent.ReviewEvent,
        changesets: Collection[api.changeset.Changeset],
        *,
        branchupdate: Optional[api.branchupdate.BranchUpdate] = None,
        commits: Optional[api.commitset.CommitSet] = None,
    ) -> None:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        for changeset in changesets:
            completion_level = await changeset.completion_level
            assert "changedlines" in completion_level, repr(completion_level)

        await add_changesets(self, event, changesets, branchupdate, commits)

    async def pingReview(self, message: str) -> api.reviewping.ReviewPing:
        return await ping_review(self.transaction, self.subject, message)

    async def setTargetBranch(self, target_branch: api.branch.Branch) -> None:
        repository = await self.subject.repository
        commits = await self.subject.commits
        branch = await self.subject.branch
        if branch:
            head = await branch.head
        else:
            (head,) = commits.heads
        commits_behind = await commits_behind_target_branch(
            repository, head, target_branch, commits
        )
        async with self.update(
            integration={
                "target_branch": target_branch.id,
                "commits_behind": commits_behind,
            }
        ) as update:
            update.set(
                integration_target=target_branch,
                integration_behind=commits_behind,
            )

    async def deleteReview(self, *, deleting_repository: bool = False) -> None:
        if self.subject.state != "draft":
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        await super().delete()

        if not deleting_repository and await self.subject.branch:
            await (await self.modifyBranch()).deleteBranch()

    @staticmethod
    async def create(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        owners: Iterable[api.user.User],
        head: Optional[api.commit.Commit],
        commits: Optional[Iterable[api.commit.Commit]],
        branch: Optional[api.branch.Branch],
        target_branch: Optional[api.branch.Branch],
        via_push: bool,
    ) -> ModifyReview:
        return ModifyReview(
            transaction,
            await CreateReview.make(
                transaction,
                repository,
                owners,
                head,
                commits,
                branch,
                target_branch,
                via_push,
            ),
        )


from .submitchanges import submit_changes
from .discardchanges import discard_changes
from .markchangeasreviewed import mark_change_as_reviewed
from .markchangeaspending import mark_change_as_pending
from .addchangesets import add_changesets
from .pingreview import ping_review
