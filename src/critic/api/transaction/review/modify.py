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
    Literal,
    Optional,
    overload,
    Union,
)

logger = logging.getLogger(__name__)

from . import (
    CreatedReview,
    CreatedReviewEvent,
    CreatedBatch,
    CreatedReviewIntegrationRequest,
    CreatedReviewFilter,
    CreatedReviewPing,
    ReviewUser,
)
from .updatereviewtags import UpdateReviewTags
from .. import Transaction, Query, Insert, InsertMany, Update, Delete, Modifier

from critic import api
from critic import dbaccess


class ModifyReview(Modifier[api.review.Review, CreatedReview]):
    def __init__(
        self, transaction: Transaction, review: Union[api.review.Review, CreatedReview]
    ) -> None:
        super().__init__(transaction, review)
        if self.is_real:
            transaction.lock("reviews", id=self.real.id)
            transaction.items.append(
                Query(
                    """UPDATE reviews
                          SET serial=serial + 1
                        WHERE id={review}""",
                    review=review,
                )
            )

    def __raiseUnlessPublished(self) -> None:
        if self.subject.state == "draft":
            raise api.review.Error("Review has not been published")

    async def publishReview(self) -> None:
        from .publish import publish

        if self.subject.state != "draft":
            raise api.review.Error("Review already published")

        if await self.subject.initial_commits_pending:
            raise api.review.Error("Initial commits still pending")

        publish(self.transaction, self.subject)

    async def closeReview(self) -> None:
        if self.subject.state != "open":
            raise api.review.Error("Only open reviews can be closed")
        if not await self.real.is_accepted:
            raise api.review.Error("Only accepted reviews can be closed")

        self.transaction.items.append(
            Update("reviews").set(state="closed").where(id=self.subject)
        )
        self.transaction.items.append(
            Delete("reviewusertags").where(review=self.subject)
        )

        CreatedReviewEvent.ensure(self.transaction, self.subject, "closed")

    async def dropReview(self) -> None:
        if self.subject.state != "open":
            raise api.review.Error("Only open reviews can be dropped")
        if await self.real.is_accepted:
            raise api.review.Error("Accepted review can not be dropped")

        self.transaction.items.append(
            Update("reviews").set(state="dropped").where(id=self.subject)
        )
        self.transaction.items.append(
            Delete("reviewusertags").where(review=self.subject)
        )

        CreatedReviewEvent.ensure(self.transaction, self.subject, "dropped")

    def reopenReview(self) -> None:
        if self.subject.state not in ("closed", "dropped"):
            raise api.review.Error("Only closed or dropped reviews can be reopened")

        self.transaction.items.append(Update(self.subject).set(state="open"))
        self.transaction.finalizers.add(UpdateReviewTags(self.real))

        CreatedReviewEvent.ensure(self.transaction, self.subject, "reopened")

    def setSummary(self, new_summary: str) -> None:
        self.transaction.items.append(Update(self.subject).set(summary=new_summary))

    def setDescription(self, new_description: str) -> None:
        self.transaction.items.append(
            Update(self.subject).set(description=new_description)
        )

    async def setOwners(self, new_owners: Iterable[api.user.User]) -> None:
        new_owners = set(new_owners)
        current_owners = await self.real.owners

        added_owners = set(new_owners) - current_owners
        removed_owners = current_owners - set(new_owners)

        for user in added_owners:
            ReviewUser.ensure(self.transaction, self.real, user, is_owner=True)
        for user in removed_owners:
            ReviewUser.ensure(self.transaction, self.real, user, is_owner=False)

    async def createComment(
        self,
        comment_type: api.comment.CommentType,
        author: api.user.User,
        text: str,
        location: api.comment.Location = None,
    ) -> ModifyComment:
        self.__raiseUnlessPublished()
        return await ModifyComment.create(
            self.transaction, self.real, comment_type, author, text, location
        )

    async def modifyComment(self, comment: api.comment.Comment) -> ModifyComment:
        if await comment.review != self.subject:
            raise api.review.Error("Cannot modify comment belonging to another review")

        # Users are not (generally) allowed to modify other users' draft
        # comments.
        if comment.is_draft:
            api.PermissionDenied.raiseUnlessUser(
                self.transaction.critic, await comment.author
            )

        return ModifyComment(self.transaction, comment)

    async def setBranch(self, branch: Union[api.branch.Branch, CreatedBranch]) -> None:
        if await self.subject.branch is not None:
            raise api.review.Error("Review already has a branch set")

        self.transaction.items.append(Update(self.subject).set(branch=branch))

        # FIXME: This seems to imply a single review event may map to multiple
        #        branch update records, which `ReviewEvent.branchupdate` doesn't
        #        really support.

        event = CreatedReviewEvent.ensure(
            self.transaction, self.subject, "branchupdate"
        )

        self.transaction.tables.add("reviewupdates")
        self.transaction.items.append(
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

    async def modifyBranch(self) -> ModifyBranch:
        branch = await self.subject.branch
        if branch is None:
            raise api.review.Error("Review has no branch")
        return ModifyBranch(self.transaction, branch)

    @overload
    async def prepareRebase(
        self, *, new_upstream: str, branch: api.branch.Branch = None
    ) -> ModifyRebase:
        ...

    @overload
    async def prepareRebase(
        self, *, history_rewrite: Literal[True], branch: api.branch.Branch = None
    ) -> ModifyRebase:
        ...

    async def prepareRebase(
        self,
        *,
        new_upstream: str = None,
        history_rewrite: Literal[True] = None,
        branch: api.branch.Branch = None,
    ) -> ModifyRebase:
        self.__raiseUnlessPublished()
        return await prepare_rebase(
            self.transaction, self.real, new_upstream, bool(history_rewrite), branch
        )

    def modifyRebase(self, rebase: api.log.rebase.Rebase) -> ModifyRebase:
        return ModifyRebase(self.transaction, rebase)

    def finishRebase(
        self,
        rebase: api.log.rebase.Rebase,
        branchupdate: api.branchupdate.BranchUpdate,
        new_upstream: api.commit.Commit = None,
        *,
        equivalent_merge: api.commit.Commit = None,
        replayed_rebase: api.commit.Commit = None,
    ) -> None:
        updates: Dict[str, dbaccess.Parameter] = {"branchupdate": branchupdate}

        if isinstance(rebase, api.log.rebase.HistoryRewrite):
            assert new_upstream is None
            assert equivalent_merge is None
            assert replayed_rebase is None
        else:
            assert isinstance(new_upstream, api.commit.Commit)
            updates["new_upstream"] = new_upstream
            assert equivalent_merge is None or replayed_rebase is None
            if equivalent_merge is not None:
                assert isinstance(equivalent_merge, api.commit.Commit)
                updates["equivalent_merge"] = equivalent_merge
            if replayed_rebase is not None:
                assert isinstance(replayed_rebase, api.commit.Commit)
                updates["replayed_rebase"] = replayed_rebase

        self.transaction.tables.add("reviewrebases")
        self.transaction.items.append(
            Update("reviewrebases").set(**updates).where(id=rebase)
        )

    def recordRebase(
        self,
        branchupdate: Union[api.branchupdate.BranchUpdate, CreatedBranchUpdate],
        *,
        old_upstream: api.commit.Commit = None,
        new_upstream: api.commit.Commit = None,
    ) -> CreatedRebase:
        event = CreatedReviewEvent.ensure(
            self.transaction,
            self.subject,
            "branchupdate",
            user=api.user.system(self.transaction.critic),
        )

        self.transaction.items.append(
            Insert("reviewupdates").values(branchupdate=branchupdate, event=event)
        )

        return CreatedRebase(self.transaction, self.real, is_pending=False).insert(
            review=self.subject,
            branchupdate=branchupdate,
            old_upstream=old_upstream,
            new_upstream=new_upstream,
        )

    async def submitChanges(self, batch_comment: CreatedComment = None) -> CreatedBatch:
        self.__raiseUnlessPublished()
        return await submit_changes(self.transaction, self.real, batch_comment)

    async def discardChanges(self, discard: Container[api.batch.DiscardValue]) -> None:
        self.__raiseUnlessPublished()
        await discard_changes(self.transaction, self.real, discard)

    async def markChangeAsReviewed(
        self, rfc: api.reviewablefilechange.ReviewableFileChange
    ) -> None:
        self.__raiseUnlessPublished()
        await mark_change_as_reviewed(self.transaction, rfc)

    async def markChangeAsPending(
        self, rfc: api.reviewablefilechange.ReviewableFileChange
    ) -> None:
        self.__raiseUnlessPublished()
        await mark_change_as_pending(self.transaction, rfc)

    async def recordBranchUpdate(
        self, branchupdate: api.branchupdate.BranchUpdate
    ) -> CreatedReviewEvent:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        event = CreatedReviewEvent.ensure(
            self.transaction,
            self.subject,
            "branchupdate",
            user=await branchupdate.updater,
        )

        assert event

        self.transaction.items.append(
            Insert("reviewupdates").values(branchupdate=branchupdate, event=event)
        )

        return event

    async def addCommits(
        self,
        branchupdate: api.branchupdate.BranchUpdate,
        commits: Iterable[api.commit.Commit],
    ) -> None:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        self.transaction.items.append(
            InsertMany(
                "reviewcommits",
                ["review", "branchupdate", "commit"],
                (
                    dict(review=self.subject, branchupdate=branchupdate, commit=commit)
                    for commit in commits
                ),
            )
        )

    @overload
    async def addChangesets(
        self,
        changesets: Collection[api.changeset.Changeset],
        *,
        branchupdate: api.branchupdate.BranchUpdate,
    ) -> None:
        ...

    @overload
    async def addChangesets(
        self,
        changesets: Collection[api.changeset.Changeset],
        *,
        commits: api.commitset.CommitSet,
    ) -> None:
        ...

    async def addChangesets(
        self,
        changesets: Collection[api.changeset.Changeset],
        *,
        branchupdate: api.branchupdate.BranchUpdate = None,
        commits: api.commitset.CommitSet = None,
    ) -> None:
        api.PermissionDenied.raiseUnlessService("reviewupdater")

        for changeset in changesets:
            completion_level = await changeset.completion_level
            assert "changedlines" in completion_level, repr(completion_level)

        await add_changesets(
            self.transaction, self.real, changesets, branchupdate, commits
        )

    async def requestIntegration(
        self,
        do_squash: bool,
        squash_message: Optional[str],
        do_autosquash: bool,
        do_integrate: bool,
    ) -> CreatedReviewIntegrationRequest:
        return await create_integration_request(
            self.transaction,
            self.real,
            do_squash,
            squash_message,
            do_autosquash,
            do_integrate,
        )

    def createFilter(
        self,
        subject: api.user.User,
        filter_type: api.reviewfilter.FilterType,
        path: str,
        default_scope: bool,
        scopes: Collection[api.reviewscope.ReviewScope],
    ) -> CreatedReviewFilter:
        return create_filter(
            self.transaction,
            self.real,
            subject,
            filter_type,
            path,
            default_scope,
            scopes,
        )

    async def deleteFilter(self, filter: api.reviewfilter.ReviewFilter) -> None:
        if await filter.review != self.subject:
            raise api.review.Error("Cannot delete filter belonging to another review")
        await delete_filter(self.transaction, self.real, filter)

    async def pingReview(self, message: str) -> CreatedReviewPing:
        return await ping_review(self.transaction, self.real, message)

    async def deleteReview(self, *, deleting_repository: bool = False) -> None:
        if self.subject.state != "draft":
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        super().delete()

        if not deleting_repository and await self.subject.branch:
            await (await self.modifyBranch()).deleteBranch()

    @staticmethod
    async def create(
        transaction: Transaction,
        repository: api.repository.Repository,
        owners: Iterable[api.user.User],
        head: Optional[api.commit.Commit],
        commits: Optional[Iterable[api.commit.Commit]],
        branch: Optional[Union[api.branch.Branch, CreatedBranch]],
        target_branch: Optional[api.branch.Branch],
        via_push: bool,
    ) -> ModifyReview:
        return ModifyReview(
            transaction,
            await create_review(
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


from .create import create_review
from .preparerebase import prepare_rebase
from .submitchanges import submit_changes
from .discardchanges import discard_changes
from .markchangeasreviewed import mark_change_as_reviewed
from .markchangeaspending import mark_change_as_pending
from .addchangesets import add_changesets
from .integrationrequest import create_integration_request
from .createfilter import create_filter
from .deletefilter import delete_filter
from .pingreview import ping_review
from ..comment import CreatedComment, ModifyComment
from ..branch import CreatedBranch, CreatedBranchUpdate, ModifyBranch
from ..rebase import CreatedRebase, ModifyRebase
