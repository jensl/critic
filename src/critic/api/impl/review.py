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

import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Callable,
    Optional,
    Collection,
    Tuple,
    Set,
    Dict,
    Sequence,
    List,
    Iterable,
    Mapping,
    cast,
)


logger = logging.getLogger(__name__)

from critic import api
from critic.api import review as public
from critic import auth
from critic.base.types import BooleanWithReason
from critic import dbaccess
from ..apiobject import Actual
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult, join

PROGRESS = "Review.progress"
TAGS = "Review.tags"
LAST_CHANGED = "Review.last_changed"


@dataclass
class Progress:
    __reviewing: float
    __open_issues: int

    @property
    def reviewing(self) -> float:
        return self.__reviewing

    @property
    def open_issues(self) -> int:
        return self.__open_issues


@dataclass(frozen=True)
class Integration:
    __target_branch: api.branch.Branch
    __commits_behind: Optional[int]
    __state: public.IntegrationState
    __squashed: bool
    __autosquashed: bool
    __strategy_used: Optional[public.IntegrationStrategy]
    __conflicts: Collection[api.file.File]
    __error_message: Optional[str]

    @property
    def target_branch(self) -> api.branch.Branch:
        return self.__target_branch

    @property
    def commits_behind(self) -> Optional[int]:
        return self.__commits_behind

    @property
    def state(self) -> public.IntegrationState:
        return self.__state

    @property
    def squashed(self) -> bool:
        return self.__squashed

    @property
    def autosquashed(self) -> bool:
        return self.__autosquashed

    @property
    def strategy_used(self) -> Optional[public.IntegrationStrategy]:
        return self.__strategy_used

    @property
    def conflicts(self) -> Collection[api.file.File]:
        return self.__conflicts

    @property
    def error_message(self) -> Optional[str]:
        return self.__error_message


@dataclass(frozen=True)
class CommitChangeCount:
    __commit_id: int
    __total_changes: int
    __reviewed_changes: int

    @property
    def commit_id(self) -> int:
        return self.__commit_id

    @property
    def total_changes(self) -> int:
        return self.__total_changes

    @property
    def reviewed_changes(self) -> int:
        return self.__reviewed_changes


PublicType = public.Review
ArgumentsType = Tuple[
    int,
    int,
    Optional[int],
    public.State,
    Optional[str],
    Optional[str],
    Optional[int],
    Optional[int],
    Optional[int],
    bool,
]


class Review(PublicType, APIObjectImplWithId, module=public):
    __is_accepted: Optional[bool]
    __owner_ids: Optional[Collection[int]]
    __assigned_reviewer_ids: Optional[Collection[int]]
    __active_reviewer_ids: Optional[Collection[int]]
    __watcher_ids: Optional[Collection[int]]
    __user_ids: Optional[Collection[int]]
    __commits: Optional[api.commitset.CommitSet]
    __changesets: Optional[Dict[api.commit.Commit, api.changeset.Changeset]]
    __files: Optional[Collection[api.file.File]]
    __issues: Optional[Sequence[api.comment.Issue]]
    __notes: Optional[Sequence[api.comment.Note]]
    __open_issues: Optional[Sequence[api.comment.Issue]]
    __progress: Optional[PublicType.Progress]
    __total_progress: Optional[float]
    __progress_per_commit: Optional[List[public.CommitChangeCount]]
    __reviewtag_ids: Optional[Set[int]]
    __last_changed: Optional[datetime.datetime]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__repository_id,
            self.__branch_id,
            self.__state,
            self.__summary,
            self.__description,
            self.__integration_target_id,
            self.__integration_branchupdate_id,  # type: ignore
            self.__integration_behind,
            self.__integration_performed,  # type: ignore
        ) = args

        self.__is_accepted = None
        self.__owner_ids = None
        self.__assigned_reviewer_ids = None
        self.__active_reviewer_ids = None
        self.__watcher_ids = None
        self.__user_ids = None
        self.__commits = None
        self.__changesets = None
        self.__files = None
        self.__issues = None
        self.__notes = None
        self.__open_issues = None
        self.__progress = None
        self.__total_progress = None
        self.__progress_per_commit = None
        self.__reviewtag_ids = None
        self.__last_changed = None
        return self.__id

    async def checkAccess(self) -> None:
        # Access the repository object to trigger an access control check.
        await self.repository

    @staticmethod
    async def filterInaccessible(
        reviews: Iterable[Review],
    ) -> Sequence[Review]:
        result = []
        for review in reviews:
            try:
                await review.checkAccess()
            except auth.AccessDenied:
                pass
            else:
                result.append(review)
        return result

    @property
    def id(self) -> int:
        return self.__id

    @property
    def state(self) -> public.State:
        return self.__state

    @property
    def summary(self) -> Optional[str]:
        return self.__summary

    @property
    def description(self) -> Optional[str]:
        return self.__description

    @property
    async def can_publish(self) -> BooleanWithReason:
        if self.state != "draft":
            return BooleanWithReason("Review already published")
        if not self.summary:
            return BooleanWithReason("Review summary not set")
        if self.__branch_id is None:
            return BooleanWithReason("Review branch not set")
        if await self.initial_commits_pending:
            return BooleanWithReason("Initial commits still pending")
        return BooleanWithReason()

    @property
    async def can_close(self) -> BooleanWithReason:
        if self.state != "open":
            return BooleanWithReason("Only open reviews can be closed")
        if not await self.is_accepted:
            return BooleanWithReason("Only accepted reviews can be closed")
        return BooleanWithReason()

    @property
    async def can_drop(self) -> BooleanWithReason:
        if self.state != "open":
            return BooleanWithReason("Only open reviews can be dropped")
        if await self.is_accepted:
            return BooleanWithReason("Aaccepted review can not be dropped")
        return BooleanWithReason()

    @property
    async def can_reopen(self) -> BooleanWithReason:
        if self.state not in ("closed", "dropped"):
            return BooleanWithReason("Only closed or dropped reviews can be reopened")
        return BooleanWithReason()

    @property
    async def is_accepted(self) -> bool:
        if self.__is_accepted is None:
            self.__is_accepted = False
            if await self.initial_commits_pending:
                return False
            async with api.critic.Query[int](
                self.critic,
                """SELECT 1
                     FROM comments
                    WHERE review={review_id}
                      AND batch IS NOT NULL
                      AND type='issue'
                      AND issue_state='open'
                    LIMIT 1""",
                review_id=self.id,
            ) as result:
                if not await result.empty():
                    logger.debug(
                        "r/%d: is_accepted=False because there are open issues", self.id
                    )
                    return False
            async with api.critic.Query[int](
                self.critic,
                """SELECT 1
                     FROM reviewfiles
                    WHERE review={review_id}
                      AND NOT reviewed
                    LIMIT 1""",
                review_id=self.id,
            ) as result:
                if not await result.empty():
                    logger.debug(
                        "r/%d: is_accepted=False because there are unreviewed files",
                        self.id,
                    )
                    return False
            self.__is_accepted = True
        return self.__is_accepted

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    async def branch(self) -> Optional[api.branch.Branch]:
        if self.__branch_id is None:
            return None
        return await api.branch.fetch(self.critic, self.__branch_id)

    async def __fetchOwnerIds(self) -> None:
        if self.__owner_ids is None:
            async with api.critic.Query[int](
                self.critic,
                """SELECT uid
                     FROM reviewusers
                    WHERE review={review_id}
                      AND owner""",
                review_id=self.id,
            ) as result:
                self.__owner_ids = frozenset(await result.scalars())

    @property
    async def owners(self) -> Collection[api.user.User]:
        await self.__fetchOwnerIds()
        assert self.__owner_ids is not None
        return frozenset(await api.user.fetchMany(self.critic, self.__owner_ids))

    async def __fetchAssignedReviewerIds(self) -> None:
        if self.__assigned_reviewer_ids is None:
            async with api.critic.Query[int](
                self.critic,
                """SELECT DISTINCT uid
                     FROM reviewuserfiles
                     JOIN reviewfiles
                            ON (reviewfiles.id=reviewuserfiles.file)
                    WHERE reviewfiles.review={review_id}""",
                review_id=self.id,
            ) as result:
                self.__assigned_reviewer_ids = frozenset(await result.scalars())

    @property
    async def assigned_reviewers(self) -> Collection[api.user.User]:
        await self.__fetchAssignedReviewerIds()
        assert self.__assigned_reviewer_ids is not None
        return frozenset(
            await api.user.fetchMany(self.critic, self.__assigned_reviewer_ids)
        )

    async def __fetchActiveReviewerIds(self) -> None:
        if self.__active_reviewer_ids is None:
            async with api.critic.Query[int](
                self.critic,
                """SELECT DISTINCT uid
                     FROM reviewuserfilechanges
                     JOIN reviewfiles
                            ON (reviewfiles.id=reviewuserfilechanges.file)
                    WHERE reviewfiles.review={review_id}""",
                review_id=self.id,
            ) as result:
                self.__active_reviewer_ids = frozenset(await result.scalars())

    @property
    async def active_reviewers(self) -> Collection[api.user.User]:
        await self.__fetchActiveReviewerIds()
        assert self.__active_reviewer_ids is not None
        return frozenset(
            await api.user.fetchMany(self.critic, self.__active_reviewer_ids)
        )

    async def __fetchWatcherIds(self) -> None:
        if self.__watcher_ids is None:
            # Find all users associated in any way with the review.
            watcher_ids = set(await self.__fetchUserIds())

            # Subtract owners and (assigned and/or active) reviewers.
            await self.__fetchOwnerIds()
            assert self.__owner_ids is not None
            watcher_ids.difference_update(self.__owner_ids)

            await self.__fetchAssignedReviewerIds()
            assert self.__assigned_reviewer_ids is not None
            watcher_ids.difference_update(self.__assigned_reviewer_ids)

            await self.__fetchActiveReviewerIds()
            assert self.__active_reviewer_ids is not None
            watcher_ids.difference_update(self.__active_reviewer_ids)

            self.__watcher_ids = frozenset(watcher_ids)

    @property
    async def watchers(self) -> Collection[api.user.User]:
        await self.__fetchWatcherIds()
        assert self.__watcher_ids is not None
        return frozenset(await api.user.fetchMany(self.critic, self.__watcher_ids))

    async def __fetchUserIds(self) -> Collection[int]:
        if self.__user_ids is None:
            # Find all users associated in any way with the review.
            async with api.critic.Query[int](
                self.critic,
                """SELECT uid
                     FROM reviewusers
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                self.__user_ids = frozenset(await result.scalars())
        return self.__user_ids

    @property
    async def users(self) -> Collection[api.user.User]:
        await self.__fetchUserIds()
        assert self.__user_ids is not None
        return frozenset(await api.user.fetchMany(self.critic, self.__user_ids))

    @property
    async def commits(self) -> api.commitset.CommitSet:
        if self.__commits is None:
            critic = self.critic
            async with api.critic.Query[int](
                critic,
                """SELECT commit
                     FROM reviewcommits
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            self.__commits = await api.commitset.create(
                critic, await api.commit.fetchMany(await self.repository, commit_ids)
            )
        return self.__commits

    @property
    async def changesets(
        self,
    ) -> Optional[Mapping[api.commit.Commit, api.changeset.Changeset]]:
        if self.__changesets is None:
            critic = self.critic
            if await self.initial_commits_pending:
                return None
            async with api.critic.Query[int](
                critic,
                """SELECT changeset
                     FROM reviewchangesets
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                changeset_ids = await result.scalars()
            self.__changesets = {
                (await changeset.to_commit): changeset
                for changeset in await api.changeset.fetchMany(
                    self.critic, changeset_ids
                )
                if not (await changeset.to_commit).is_merge
            }
        return self.__changesets

    @property
    async def files(self) -> Collection[api.file.File]:
        if self.__files is None:
            async with api.critic.Query[int](
                self.critic,
                """SELECT DISTINCT file
                     FROM reviewfiles
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                file_ids = await result.scalars()
            self.__files = frozenset(await api.file.fetchMany(self.critic, file_ids))
        return self.__files

    @property
    async def pending_rebase(self) -> Optional[api.rebase.Rebase]:
        rebases = await api.rebase.fetchAll(self.critic, review=self, pending=True)
        if rebases:
            assert len(rebases) == 1
            return rebases[0]
        return None

    @property
    async def issues(self) -> Sequence[api.comment.Issue]:
        if self.__issues is None:
            self.__issues = cast(
                Sequence[api.comment.Issue],
                await api.comment.fetchAll(
                    self.critic, review=self, comment_type="issue"
                ),
            )
        return self.__issues

    @property
    async def open_issues(self) -> Sequence[api.comment.Issue]:
        if self.__open_issues is None:
            self.__open_issues = [
                issue for issue in await self.issues if issue.state == "open"
            ]
        return self.__open_issues

    @property
    async def notes(self) -> Sequence[api.comment.Note]:
        if self.__notes is None:
            self.__notes = cast(
                Sequence[api.comment.Note],
                await api.comment.fetchAll(
                    self.critic, review=self, comment_type="note"
                ),
            )
        return self.__notes

    async def isReviewableCommit(self, commit: api.commit.Commit) -> bool:
        async with api.critic.Query[int](
            self.critic,
            """SELECT 1
                 FROM reviewchangesets AS rc
                 JOIN changesets ON (changesets.id=rc.changeset)
                WHERE review={review_id}
                  AND to_commit={commit}
                LIMIT 1""",
            review_id=self.id,
            commit=commit,
        ) as result:
            return not await result.empty()

    @staticmethod
    async def __fetchProgress(critic: api.critic.Critic) -> None:
        cached_reviews = Review.allCached()

        review_ids = []
        for review in cached_reviews.values():
            if review.__progress is None:
                review_ids.append(review.id)

        def zero_counts() -> List[int]:
            return [0, 0]

        counts_per_review: Dict[int, List[int]] = defaultdict(zero_counts)
        async with api.critic.Query[Tuple[int, bool, int]](
            critic,
            """SELECT review, reviewed, SUM(inserted + deleted)
                 FROM reviewfiles
                WHERE review=ANY({review_ids})
             GROUP BY review, reviewed""",
            review_ids=review_ids,
        ) as files_result:
            async for review_id, is_reviewed, count in files_result:
                counts_per_review[review_id][int(is_reviewed)] += max(1, count)

        open_issues_per_review: Dict[int, int] = defaultdict(lambda: 0)
        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT review, COUNT(id)
                 FROM comments
                WHERE review=ANY({review_ids})
                  AND type='issue'
                  AND issue_state='open'
             GROUP BY review""",
            review_ids=review_ids,
        ) as comments_result:
            async for review_id, open_issues in comments_result:
                open_issues_per_review[review_id] = open_issues

        for review_id in review_ids:
            review = cached_reviews[review_id]
            counts = counts_per_review[review_id]
            open_issues = open_issues_per_review[review_id]
            reviewed_count = counts[1]
            total_count = sum(counts)
            review.__progress = Progress(
                (float(reviewed_count) / total_count) if total_count else 0, open_issues
            )

    @property
    async def progress(self) -> PublicType.Progress:
        if self.__progress is None:
            await Review.__fetchProgress(self.critic)
            assert self.__progress is not None
        return self.__progress

    @property
    async def total_progress(self) -> float:
        if self.__total_progress is None:
            reviewed = 0
            pending = 0

            async with api.critic.Query[Tuple[bool, int]](
                self.critic,
                """SELECT reviewed, SUM(inserted + deleted)
                     FROM reviewfiles
                    WHERE review={review_id}
                 GROUP BY reviewed""",
                review_id=self.id,
            ) as result:
                async for is_reviewed, modifications in result:
                    if modifications == 0:  # binary file change
                        actual_modifications = 1
                    else:
                        actual_modifications = modifications
                    if is_reviewed:
                        reviewed = actual_modifications
                    else:
                        pending = actual_modifications

            total = reviewed + pending
            if reviewed == 0:
                self.__total_progress = 0
            elif pending == 0:
                self.__total_progress = 1
            else:
                self.__total_progress = reviewed / float(total)
        return self.__total_progress

    @property
    async def progress_per_commit(self) -> Sequence[public.CommitChangeCount]:
        if self.__progress_per_commit is None:
            total_changes_dict = {}
            reviewed_changes_dict = {}

            async with api.critic.Query[Tuple[int, int]](
                self.critic,
                """SELECT to_commit, SUM(deleted + inserted)
                     FROM reviewfiles AS rf
                     JOIN changesets ON (changesets.id=rf.changeset)
                    WHERE review={review_id}
                 GROUP BY to_commit""",
                review_id=self.id,
            ) as result:
                async for commit_id, changes in result:
                    total_changes_dict[commit_id] = changes
            async with api.critic.Query[Tuple[int, int]](
                self.critic,
                """SELECT to_commit, SUM(deleted + inserted)
                     FROM reviewfiles AS rf
                     JOIN changesets ON (changesets.id=rf.changeset)
                    WHERE review={review_id}
                      AND reviewed
                 GROUP BY to_commit""",
                review_id=self.id,
            ) as result:
                async for commit_id, changes in result:
                    reviewed_changes_dict[commit_id] = changes

            commit_change_counts: List[public.CommitChangeCount] = []
            for commit_id, total_changes in sorted(total_changes_dict.items()):
                reviewed_changes = reviewed_changes_dict.get(commit_id, 0)

                commit_change_counts.append(
                    CommitChangeCount(commit_id, total_changes, reviewed_changes)
                )

            self.__progress_per_commit = commit_change_counts
        return self.__progress_per_commit

    @property
    async def initial_commits_pending(self) -> bool:
        async with api.critic.Query[int](
            self.critic,
            """SELECT 1
                 FROM reviewcommits
                WHERE review={review_id}
                  AND commit NOT IN (
                    SELECT to_commit
                      FROM changesets
                      JOIN reviewchangesets ON (changeset=id)
                     WHERE review={review_id}
                  )
                LIMIT 1""",
            review_id=self.id,
        ) as result:
            return not await result.empty()

    @property
    async def pending_update(self) -> Optional[api.branchupdate.BranchUpdate]:
        async with api.critic.Query[int](
            self.critic,
            """SELECT id
                 FROM branchupdates
      LEFT OUTER JOIN reviewupdates ON (branchupdate=id)
                WHERE branch={branch}
                  AND event IS NULL""",
            branch=self.__branch_id,
        ) as result:
            try:
                branchupdate_id = await result.scalar()
            except dbaccess.ZeroRowsInResult:
                return None

        return await api.branchupdate.fetch(self.critic, branchupdate_id)

    @staticmethod
    async def __fetchTags(critic: api.critic.Critic) -> None:
        cached_reviews = Review.allCached()

        review_ids = []
        for review in cached_reviews.values():
            if review.__reviewtag_ids is None:
                review_ids.append(review.id)

        reviewtag_ids: Dict[int, Set[int]] = defaultdict(set)
        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT review, tag
                 FROM reviewusertags
                WHERE review=ANY({review_ids})
                  AND uid={user}""",
            review_ids=review_ids,
            user=critic.effective_user,
        ) as result:
            async for review_id, tag_id in result:
                reviewtag_ids[review_id].add(tag_id)

        for review_id in review_ids:
            review = cached_reviews[review_id]
            review.__reviewtag_ids = reviewtag_ids[review_id]

    @property
    async def tags(self) -> Sequence[api.reviewtag.ReviewTag]:
        if self.__reviewtag_ids is None:
            await Review.__fetchTags(self.critic)
            assert self.__reviewtag_ids is not None
        return await api.reviewtag.fetchMany(self.critic, self.__reviewtag_ids)

    @staticmethod
    async def __fetchLastChanged(critic: api.critic.Critic) -> None:
        cached_reviews = Review.allCached()

        review_ids = []
        for review in cached_reviews.values():
            if review.__last_changed is None:
                review_ids.append(review.id)

        last_changed = {}
        async with api.critic.Query[Tuple[int, datetime.datetime]](
            critic,
            """SELECT review, MAX(time)::TIMESTAMP AS time
                 FROM reviewevents
                WHERE review=ANY({review_ids})
             GROUP BY review""",
            review_ids=review_ids,
        ) as result:
            async for review_id, timestamp in result:
                last_changed[review_id] = timestamp

        for review_id in review_ids:
            review = cached_reviews[review_id]
            review.__last_changed = last_changed[review_id]

    @property
    async def last_changed(self) -> datetime.datetime:
        if self.__last_changed is None:
            await Review.__fetchLastChanged(self.critic)
            assert self.__last_changed is not None
        return self.__last_changed

    async def prefetchCommits(self) -> None:
        commit_ids: Set[int]
        async with api.critic.Query[int](
            self.critic,
            """SELECT commit
                 FROM reviewcommits
                WHERE review={review_id}""",
            review_id=self.id,
        ) as commit_result:
            commit_ids = set(await commit_result.scalars())
        async with api.critic.Query[
            Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
        ](
            self.critic,
            """SELECT old_upstream, new_upstream, equivalent_merge,
                      replayed_rebase
                 FROM reviewrebases
                WHERE review={review_id}""",
            review_id=self.id,
        ) as rebases_result:
            async for (
                old_upstream,
                new_upstream,
                equivalent_merge,
                replayed_rebase,
            ) in rebases_result:
                if old_upstream is not None:
                    commit_ids.add(old_upstream)
                if new_upstream is not None:
                    commit_ids.add(new_upstream)
                if equivalent_merge is not None:
                    commit_ids.add(equivalent_merge)
                if replayed_rebase is not None:
                    commit_ids.add(replayed_rebase)
        await api.commit.prefetch(await self.repository, commit_ids)

    @property
    async def integration(self) -> Optional[PublicType.Integration]:
        if self.__integration_target_id is None:
            return None

        critic = self.critic
        state: public.IntegrationState = "planned"

        async with api.critic.Query[
            Tuple[
                bool,
                bool,
                bool,
                bool,
                bool,
                Optional[public.IntegrationStrategy],
                Optional[bool],
                Optional[str],
            ]
        ](
            critic,
            """SELECT do_squash, squashed, do_autosquash, autosquashed,
                      do_integrate, strategy_used, successful, error_message
                 FROM reviewintegrationrequests
                WHERE review={review}
             ORDER BY id DESC
                LIMIT 1""",
            review=self.id,
        ) as reviewintegrationrequests_result:
            try:
                (
                    do_squash,
                    squashed,
                    do_autosquash,
                    autosquashed,
                    do_integrate,
                    strategy_used,
                    successful,
                    error_message,
                ) = await reviewintegrationrequests_result.one()
            except reviewintegrationrequests_result.ZeroRowsInResult:
                squashed = autosquashed = False
                strategy_used = successful = None
                error_message = None
            else:
                if any(
                    (
                        (do_squash and not squashed),
                        (do_autosquash and not autosquashed),
                        (do_integrate and strategy_used is None),
                    )
                ):
                    state = "in-progress"
                elif not do_integrate:
                    pass
                elif successful:
                    state = "performed"
                else:
                    state = "failed"

        if state != "performed":
            async with api.critic.Query[int](
                critic,
                """SELECT file
                     FROM reviewintegrationconflicts
                    WHERE review={review}""",
                review=self.id,
            ) as reviewintegrationconflicts_result:
                file_ids = await reviewintegrationconflicts_result.scalars()
            conflicts = frozenset(await api.file.fetchMany(critic, file_ids))
        else:
            conflicts = frozenset()

        return Integration(
            await api.branch.fetch(critic, self.__integration_target_id),
            self.__integration_behind,
            state,
            squashed,
            autosquashed,
            strategy_used,
            conflicts,
            error_message,
        )

    @classmethod
    def refresh_tables(cls) -> Set[str]:
        return {
            "reviews",
            "reviewcommits",
            "reviewchangesets",
            "reviewrebases",
            "reviewuserfiles",
            "reviewusers",
            "comments",
        }

    async def refresh(self: Actual) -> Actual:
        logger.debug("refreshing: r/%d", self.__id)
        return await super().refresh()

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "repository",
    "branch",
    "state",
    "summary",
    "description",
    "integration_target",
    "integration_branchupdate",
    "integration_behind",
    "integration_performed",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    review_id: Optional[int],
    branch: Optional[api.branch.Branch],
) -> Review:
    if review_id is not None:
        return await Review.ensureOne(review_id, queries.idFetcher(critic, Review))

    assert branch is not None
    return Review.storeOne(
        await queries.query(critic, branch=branch).makeOne(
            Review, public.InvalidBranch(value=branch)
        )
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, review_ids: Sequence[int]
) -> Sequence[Review]:
    return await Review.ensure(review_ids, queries.idsFetcher(critic, Review))


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    states: Optional[Set[public.State]],
    category: Optional[public.Category],
) -> Sequence[Review]:
    joins = []
    conditions = []
    tag = None
    if repository is not None:
        conditions.append("reviews.repository={repository}")
    if category is not None:
        category_states: Set[public.State] = {"open"}
        joins.append(join(reviewusers=["reviewusers.review=reviews.id"]))
        conditions.append("reviewusers.uid={effective_user}")
        if category == "outgoing":
            category_states.add("draft")
            conditions.append("reviewusers.owner")
        else:
            joins.append(join(reviewusertags=["reviewusertags.review=reviews.id"]))
            conditions.extend(
                ["reviewusertags.uid={effective_user}", "reviewusertags.tag={tag}"]
            )
            if category == "incoming":
                tag = await api.reviewtag.fetch(critic, name="assigned")
            else:
                tag = await api.reviewtag.fetch(critic, name="watching")
        if states is None:
            states = category_states
        else:
            # Filter on the intersection if both |states| and |category| are
            # used. The only useful combination is to fetch only unpublished or
            # only open owned/outgoing reviews; all other are no-ops or lead to
            # a guaranteed empty result.
            states = states & category_states
    states_list: Optional[List[str]]
    if states is not None:
        conditions.append("state=ANY({states}::reviewstate[])")
        states_list = [*states]
    else:
        states_list = None
    return Review.store(
        await Review.filterInaccessible(
            await queries.query(
                critic,
                queries.formatQuery(*conditions, joins=joins),
                repository=repository,
                states=states_list,
                tag=tag,
                effective_user=critic.effective_user,
            ).make(Review)
        )
    )
