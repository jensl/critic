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
    Optional,
    FrozenSet,
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

from . import apiobject

from critic import api
from critic import auth
from critic import dbaccess

PROGRESS = "Review.progress"
TAGS = "Review.tags"
LAST_CHANGED = "Review.last_changed"


@dataclass(frozen=True)
class Progress:
    reviewing: float
    open_issues: int


@dataclass(frozen=True)
class Integration:
    target_branch: api.branch.Branch
    commits_behind: Optional[int]
    state: api.review.IntegrationState
    squashed: bool
    autosquashed: bool
    strategy_used: Optional[api.review.IntegrationStrategy]
    conflicts: FrozenSet[api.file.File]
    error_message: Optional[str]


@dataclass(frozen=True)
class CommitChangeCount:
    commit_id: int
    total_changes: int
    reviewed_changes: int


WrapperType = api.review.Review
ArgumentsType = Tuple[
    int,
    int,
    Optional[int],
    api.review.State,
    Optional[str],
    Optional[str],
    Optional[int],
    Optional[int],
    Optional[int],
    bool,
]


class Review(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = [
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
    ]

    __is_accepted: Optional[bool]
    __owner_ids: Optional[FrozenSet[int]]
    __assigned_reviewer_ids: Optional[FrozenSet[int]]
    __active_reviewer_ids: Optional[FrozenSet[int]]
    __watcher_ids: Optional[FrozenSet[int]]
    __commits: Optional[api.commitset.CommitSet]
    __changesets: Optional[Dict[api.commit.Commit, api.changeset.Changeset]]
    __files: Optional[FrozenSet[api.file.File]]
    __issues: Optional[Sequence[api.comment.Issue]]
    __notes: Optional[Sequence[api.comment.Note]]
    __open_issues: Optional[Sequence[api.comment.Issue]]
    __progress: Optional[api.review.Review.Progress]
    __total_progress: Optional[float]
    __progress_per_commit: Optional[List[api.review.CommitChangeCount]]
    __reviewtag_ids: Optional[Set[int]]
    __last_changed: Optional[datetime.datetime]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__repository_id,
            self.__branch_id,
            self.state,
            self.summary,
            self.description,
            self.__integration_target_id,
            self.__integration_branchupdate_id,
            self.integration_behind,
            self.integration_performed,
        ) = args

        self.__is_accepted = None
        self.__owner_ids = None
        self.__assigned_reviewer_ids = None
        self.__active_reviewer_ids = None
        self.__watcher_ids = None
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

    @staticmethod
    async def checkAccess(review: WrapperType) -> None:
        # Access the repository object to trigger an access control check.
        await review.repository

    @staticmethod
    async def filterInaccessible(
        reviews: Iterable[WrapperType],
    ) -> Sequence[WrapperType]:
        result = []
        for review in reviews:
            try:
                await Review.checkAccess(review)
            except auth.AccessDenied:
                pass
            else:
                result.append(review)
        return result

    async def isAccepted(self, critic: api.critic.Critic) -> bool:
        if self.__is_accepted is None:
            self.__is_accepted = False
            if await self.getInitialCommitsPending(critic):
                return False
            async with api.critic.Query[int](
                critic,
                """SELECT 1
                     FROM commentchains
                    WHERE review={review_id}
                      AND type='issue'
                      AND state='open'
                    LIMIT 1""",
                review_id=self.id,
            ) as result:
                if not await result.empty():
                    return False
            async with api.critic.Query[int](
                critic,
                """SELECT 1
                     FROM reviewfiles
                    WHERE review={review_id}
                      AND NOT reviewed
                    LIMIT 1""",
                review_id=self.id,
            ) as result:
                if not await result.empty():
                    return False
            self.__is_accepted = True
        return self.__is_accepted

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)

    async def getBranch(self, critic: api.critic.Critic) -> Optional[api.branch.Branch]:
        if self.__branch_id is None:
            return None
        return await api.branch.fetch(critic, self.__branch_id)

    async def __fetchOwnerIds(self, critic: api.critic.Critic) -> None:
        if self.__owner_ids is None:
            async with api.critic.Query[int](
                critic,
                """SELECT uid
                     FROM reviewusers
                    WHERE review={review_id}
                      AND owner""",
                review_id=self.id,
            ) as result:
                self.__owner_ids = frozenset(await result.scalars())

    async def getOwners(self, critic: api.critic.Critic) -> FrozenSet[api.user.User]:
        await self.__fetchOwnerIds(critic)
        assert self.__owner_ids is not None
        return frozenset(await api.user.fetchMany(critic, self.__owner_ids))

    async def __fetchAssignedReviewerIds(self, critic: api.critic.Critic) -> None:
        if self.__assigned_reviewer_ids is None:
            async with api.critic.Query[int](
                critic,
                """SELECT DISTINCT uid
                     FROM reviewuserfiles
                     JOIN reviewfiles
                            ON (reviewfiles.id=reviewuserfiles.file)
                    WHERE reviewfiles.review={review_id}""",
                review_id=self.id,
            ) as result:
                self.__assigned_reviewer_ids = frozenset(await result.scalars())

    async def getAssignedReviewers(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.user.User]:
        await self.__fetchAssignedReviewerIds(critic)
        assert self.__assigned_reviewer_ids is not None
        return frozenset(await api.user.fetchMany(critic, self.__assigned_reviewer_ids))

    async def __fetchActiveReviewerIds(self, critic: api.critic.Critic) -> None:
        if self.__active_reviewer_ids is None:
            async with api.critic.Query[int](
                critic,
                """SELECT DISTINCT uid
                     FROM reviewfilechanges
                     JOIN reviewfiles
                            ON (reviewfiles.id=reviewfilechanges.file)
                    WHERE reviewfiles.review={review_id}""",
                review_id=self.id,
            ) as result:
                self.__active_reviewer_ids = frozenset(await result.scalars())

    async def getActiveReviewers(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.user.User]:
        await self.__fetchActiveReviewerIds(critic)
        assert self.__active_reviewer_ids is not None
        return frozenset(await api.user.fetchMany(critic, self.__active_reviewer_ids))

    async def __fetchWatcherIds(self, critic: api.critic.Critic) -> None:
        if self.__watcher_ids is None:
            # Find all users associated in any way with the review.
            async with critic.query(
                """SELECT uid
                     FROM reviewusers
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                watcher_ids = set(await result.scalars())

            # Subtract owners and (assigned and/or active) reviewers.
            await self.__fetchOwnerIds(critic)
            assert self.__owner_ids is not None
            watcher_ids.difference_update(self.__owner_ids)

            await self.__fetchAssignedReviewerIds(critic)
            assert self.__assigned_reviewer_ids is not None
            watcher_ids.difference_update(self.__assigned_reviewer_ids)

            await self.__fetchActiveReviewerIds(critic)
            assert self.__active_reviewer_ids is not None
            watcher_ids.difference_update(self.__active_reviewer_ids)

            self.__watcher_ids = frozenset(watcher_ids)

    async def getWatchers(self, critic: api.critic.Critic) -> FrozenSet[api.user.User]:
        await self.__fetchWatcherIds(critic)
        assert self.__watcher_ids is not None
        return frozenset(await api.user.fetchMany(critic, self.__watcher_ids))

    async def getCommits(self, wrapper: WrapperType) -> api.commitset.CommitSet:
        if self.__commits is None:
            critic = wrapper.critic
            async with api.critic.Query[int](
                critic,
                """SELECT commit
                     FROM reviewcommits
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                commit_ids = await result.scalars()
            self.__commits = await api.commitset.create(
                critic, await api.commit.fetchMany(await wrapper.repository, commit_ids)
            )
        return self.__commits

    async def getChangesets(
        self, wrapper: WrapperType
    ) -> Optional[Mapping[api.commit.Commit, api.changeset.Changeset]]:
        if self.__changesets is None:
            critic = wrapper.critic
            if await self.getInitialCommitsPending(critic):
                return None
            async with critic.query(
                """SELECT changeset
                     FROM reviewchangesets
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                changeset_ids = await result.scalars()
            self.__changesets = {
                (await changeset.to_commit): changeset
                for changeset in await api.changeset.fetchMany(critic, changeset_ids)
                if not (await changeset.to_commit).is_merge
            }
        return self.__changesets

    async def getFiles(self, critic: api.critic.Critic) -> FrozenSet[api.file.File]:
        if self.__files is None:
            async with critic.query(
                """SELECT DISTINCT file
                     FROM reviewfiles
                    WHERE review={review_id}""",
                review_id=self.id,
            ) as result:
                file_ids = await result.scalars()
            self.__files = frozenset(await api.file.fetchMany(critic, file_ids))
        return self.__files

    async def getPendingRebase(
        self, wrapper: WrapperType
    ) -> Optional[api.log.rebase.Rebase]:
        rebases = await api.log.rebase.fetchAll(
            wrapper.critic, review=wrapper, pending=True
        )
        if rebases:
            assert len(rebases) == 1
            return rebases[0]
        return None

    async def getIssues(self, wrapper: WrapperType) -> Sequence[api.comment.Issue]:
        if self.__issues is None:
            self.__issues = cast(
                Sequence[api.comment.Issue],
                await api.comment.fetchAll(
                    wrapper.critic, review=wrapper, comment_type="issue"
                ),
            )
        return self.__issues

    async def getOpenIssues(self, wrapper: WrapperType) -> Sequence[api.comment.Issue]:
        if self.__open_issues is None:
            self.__open_issues = [
                issue
                for issue in await self.getIssues(wrapper)
                if issue.state == "open"
            ]
        return self.__open_issues

    async def getNotes(self, wrapper: WrapperType) -> Sequence[api.comment.Note]:
        if self.__notes is None:
            self.__notes = cast(
                Sequence[api.comment.Note],
                await api.comment.fetchAll(
                    wrapper.critic, review=wrapper, comment_type="note"
                ),
            )
        return self.__notes

    async def isReviewableCommit(
        self, critic: api.critic.Critic, commit: api.commit.Commit
    ) -> bool:
        async with critic.query(
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
        cached_reviews = Review.allCached(critic)

        review_ids = []
        for review in cached_reviews.values():
            if review._impl.__progress is None:
                review_ids.append(review.id)

        def zero_counts() -> List[int]:
            return [0, 0]

        counts_per_review: Dict[int, List[int]] = defaultdict(zero_counts)
        async with api.critic.Query[Tuple[int, bool, int]](
            critic,
            """SELECT review, reviewed, SUM(inserted + deleted)
                 FROM reviewfiles
                WHERE {review=review_ids:array}
             GROUP BY review, reviewed""",
            review_ids=review_ids,
        ) as files_result:
            async for review_id, is_reviewed, count in files_result:
                counts_per_review[review_id][int(is_reviewed)] += max(1, count)

        open_issues_per_review: Dict[int, int] = defaultdict(lambda: 0)
        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT review, COUNT(id)
                 FROM commentchains
                WHERE {review=review_ids:array}
                  AND type='issue'
                  AND state='open'
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
            review._impl.__progress = Progress(
                (float(reviewed_count) / total_count) if total_count else 0, open_issues
            )

    async def getProgress(self, critic: api.critic.Critic) -> WrapperType.Progress:
        async with critic._impl.criticalSection(PROGRESS):
            if self.__progress is None:
                await Review.__fetchProgress(critic)
                assert self.__progress is not None
        return self.__progress

    async def getTotalProgress(self, critic: api.critic.Critic) -> float:
        if self.__total_progress is None:
            reviewed = 0
            pending = 0

            async with api.critic.Query[Tuple[bool, int]](
                critic,
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

    async def getProgressPerCommit(
        self, critic: api.critic.Critic
    ) -> Sequence[api.review.CommitChangeCount]:
        if self.__progress_per_commit is None:
            total_changes_dict = {}
            reviewed_changes_dict = {}

            async with critic.query(
                """SELECT to_commit, SUM(deleted + inserted)
                     FROM reviewfiles AS rf
                     JOIN changesets ON (changesets.id=rf.changeset)
                    WHERE review={review_id}
                 GROUP BY to_commit""",
                review_id=self.id,
            ) as result:
                async for commit_id, changes in result:
                    total_changes_dict[commit_id] = changes
            async with critic.query(
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

            commit_change_counts: List[api.review.CommitChangeCount] = []
            for commit_id, total_changes in sorted(total_changes_dict.items()):
                reviewed_changes = reviewed_changes_dict.get(commit_id, 0)

                commit_change_counts.append(
                    CommitChangeCount(commit_id, total_changes, reviewed_changes)
                )

            self.__progress_per_commit = commit_change_counts
        return self.__progress_per_commit

    async def getInitialCommitsPending(self, critic: api.critic.Critic) -> bool:
        async with critic.query(
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

    async def getPendingUpdate(
        self, critic: api.critic.Critic
    ) -> Optional[api.branchupdate.BranchUpdate]:
        async with critic.query(
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

        return await api.branchupdate.fetch(critic, branchupdate_id)

    @staticmethod
    async def __fetchTags(critic: api.critic.Critic) -> None:
        cached_reviews = Review.allCached(critic)

        review_ids = []
        for review in cached_reviews.values():
            if review._impl.__reviewtag_ids is None:
                review_ids.append(review.id)

        reviewtag_ids: Dict[int, Set[int]] = defaultdict(set)
        async with critic.query(
            """SELECT review, tag
                 FROM reviewusertags
                WHERE {review=review_ids:array}
                  AND uid={user}""",
            review_ids=review_ids,
            user=critic.effective_user,
        ) as result:
            async for review_id, tag_id in result:
                reviewtag_ids[review_id].add(tag_id)

        for review_id in review_ids:
            review = cached_reviews[review_id]
            review._impl.__reviewtag_ids = reviewtag_ids[review_id]

    async def getTags(
        self, critic: api.critic.Critic
    ) -> Sequence[api.reviewtag.ReviewTag]:
        async with critic._impl.criticalSection(TAGS):
            if self.__reviewtag_ids is None:
                await Review.__fetchTags(critic)
                assert self.__reviewtag_ids is not None
        return await api.reviewtag.fetchMany(critic, self.__reviewtag_ids)

    @staticmethod
    async def __fetchLastChanged(critic: api.critic.Critic) -> None:
        cached_reviews = Review.allCached(critic)

        review_ids = []
        for review in cached_reviews.values():
            if review._impl.__last_changed is None:
                review_ids.append(review.id)

        last_changed = {}
        async with api.critic.Query[Tuple[int, datetime.datetime]](
            critic,
            """SELECT review, MAX(time)::TIMESTAMP AS time
                 FROM reviewevents
                WHERE {review=review_ids:array}
             GROUP BY review""",
            review_ids=review_ids,
        ) as result:
            async for review_id, timestamp in result:
                last_changed[review_id] = timestamp

        for review_id in review_ids:
            review = cached_reviews[review_id]
            review._impl.__last_changed = last_changed[review_id]

    async def getLastChanged(self, critic: api.critic.Critic) -> datetime.datetime:
        async with critic._impl.criticalSection(LAST_CHANGED):
            if self.__last_changed is None:
                await Review.__fetchLastChanged(critic)
                assert self.__last_changed is not None
        return self.__last_changed

    async def prefetchCommits(self, critic: api.critic.Critic) -> None:
        async with critic.query(
            """SELECT commit
                 FROM reviewcommits
                WHERE review={review_id}""",
            review_id=self.id,
        ) as result:
            commit_ids = set(await result.scalars())
        async with critic.query(
            """SELECT old_upstream, new_upstream, equivalent_merge,
                      replayed_rebase
                 FROM reviewrebases
                WHERE review={review_id}""",
            review_id=self.id,
        ) as result:
            async for (
                old_upstream,
                new_upstream,
                equivalent_merge,
                replayed_rebase,
            ) in result:
                commit_ids.add(old_upstream)
                commit_ids.add(new_upstream)
                commit_ids.add(equivalent_merge)
                commit_ids.add(replayed_rebase)
        try:
            commit_ids.remove(None)
        except KeyError:
            pass
        await api.commit.prefetch(await self.getRepository(critic), commit_ids)

    async def getIntegration(
        self, wrapper: WrapperType
    ) -> Optional[WrapperType.Integration]:
        if self.__integration_target_id is None:
            return None

        critic = wrapper.critic
        state: api.review.IntegrationState = "planned"

        async with critic.query(
            """SELECT do_squash, squashed, do_autosquash, autosquashed,
                      do_integrate, strategy_used, successful, error_message
                 FROM reviewintegrationrequests
                WHERE review={review}
             ORDER BY id DESC
                LIMIT 1""",
            review=self.id,
        ) as result:
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
                ) = await result.one()
            except result.ZeroRowsInResult:
                squashed = autosquashed = strategy_used = successful = None
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
            ) as result:
                file_ids = await result.scalars()
            conflicts = frozenset(await api.file.fetchMany(critic, file_ids))
        else:
            conflicts = frozenset()

        return Integration(
            await api.branch.fetch(critic, self.__integration_target_id),
            self.integration_behind,
            state,
            squashed,
            autosquashed,
            strategy_used,
            conflicts,
            error_message,
        )

    @staticmethod
    def refresh_tables() -> Set[str]:
        return {
            "reviews",
            "reviewcommits",
            "reviewchangesets",
            "reviewrebases",
            "reviewuserfiles",
            "reviewusers",
            "commentchains",
        }


@Review.cached
async def fetch(
    critic: api.critic.Critic,
    review_id: Optional[int],
    branch: Optional[api.branch.Branch],
) -> WrapperType:
    conditions = []
    if review_id is not None:
        conditions.append("id={review_id}")
    else:
        conditions.append("branch={branch}")
    async with Review.query(
        critic, conditions, review_id=review_id, branch=branch
    ) as result:
        try:
            review = await Review.makeOne(critic, result)
        except result.ZeroRowsInResult:
            assert branch
            raise api.review.InvalidBranch(branch)
    await Review.checkAccess(review)
    return review


@Review.cachedMany
async def fetchMany(
    critic: api.critic.Critic, review_ids: Iterable[int]
) -> Sequence[WrapperType]:
    async with Review.query(
        critic, ["id=ANY({review_ids})"], review_ids=list(review_ids),
    ) as result:
        reviews = await Review.make(critic, result)
    for review in reviews:
        await Review.checkAccess(review)
    return reviews


async def fetchAll(
    critic: api.critic.Critic,
    repository: Optional[api.repository.Repository],
    states: Optional[Set[api.review.State]],
    category: Optional[api.review.Category],
) -> Sequence[WrapperType]:
    tables = [Review.table()]
    conditions = ["TRUE"]
    tag = None
    if repository is not None:
        conditions.append("reviews.repository={repository}")
    if category is not None:
        category_states: Set[api.review.State] = {"open"}
        tables.append("reviewusers ON (reviewusers.review=reviews.id)")
        conditions.append("reviewusers.uid={effective_user}")
        if category != "outgoing":
            tables.append("reviewusertags ON (reviewusertags.review=reviews.id)")
            conditions.extend(
                ["reviewusertags.uid={effective_user}", "reviewusertags.tag={tag}"]
            )
        if category == "incoming":
            tag = await api.reviewtag.fetch(critic, name="assigned")
        elif category == "outgoing":
            category_states.add("draft")
            conditions.append("reviewusers.owner")
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
        states_list = list(states)
    else:
        states_list = None
    async with Review.query(
        critic,
        f"""SELECT DISTINCT {Review.columns()}
              FROM {" JOIN ".join(tables)}
             WHERE {" AND ".join(conditions)}
          ORDER BY reviews.id""",
        repository=repository,
        states=states_list,
        tag=tag,
        effective_user=critic.effective_user,
    ) as result:
        reviews = await Review.make(critic, result)
    return await Review.filterInaccessible(reviews)
