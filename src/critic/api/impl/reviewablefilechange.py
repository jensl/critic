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
from collections import defaultdict
from dataclasses import dataclass
from typing import Tuple, Optional, Iterable, Sequence, Dict, List, FrozenSet, Set

logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewablefilechange as public
from . import apiobject
from .critic import Critic

REVIEWED_BY = "ReviewableFileChange.reviewed_by"
ASSIGNED_REVIEWERS = "ReviewableFileChange.assigned_reviewers"
DRAFT_CHANGES = "ReviewableFileChange.draft_changes"


@dataclass(frozen=True)
class DraftChanges:
    __author: api.user.User
    __new_is_reviewed: bool

    @property
    def author(self) -> api.user.User:
        return self.__author

    @property
    def new_is_reviewed(self) -> bool:
        return self.__new_is_reviewed


WrapperType = api.reviewablefilechange.ReviewableFileChange
ArgumentsType = Tuple[int, int, int, int, int, int, int, bool]


class ReviewableFileChange(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.reviewablefilechange.ReviewableFileChange

    table_name = "reviewfiles"
    column_names = [
        "id",
        "review",
        "changeset",
        "file",
        "scope",
        "deleted",
        "inserted",
        "reviewed",
    ]

    __reviewed_by: Optional[FrozenSet[api.user.User]]
    __assigned_reviewers: Optional[FrozenSet[api.user.User]]
    __draft_changes: Optional[WrapperType.DraftChanges]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__review_id,
            self.__changeset_id,
            self.__file_id,
            self.__scope_id,
            self.inserted_lines,
            self.deleted_lines,
            self.is_reviewed,
        ) = args

        self.__reviewed_by = None
        self.__assigned_reviewers = None
        self.__draft_changes = None
        self.__draft_changes_fetched = False

    @property
    def changeset_id(self) -> int:
        return self.__changeset_id

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.__review_id)

    async def getChangeset(self, critic: api.critic.Critic) -> api.changeset.Changeset:
        return await api.changeset.fetch(critic, self.__changeset_id)

    async def getFile(self, critic: api.critic.Critic) -> api.file.File:
        return await api.file.fetch(critic, self.__file_id)

    async def getReviewScope(
        self, critic: api.critic.Critic
    ) -> Optional[api.reviewscope.ReviewScope]:
        if self.__scope_id is None:
            return None
        return await api.reviewscope.fetch(critic, self.__scope_id)

    async def __loadReviewedBy(self, critic: api.critic.Critic) -> None:
        cached_objects = dict(ReviewableFileChange.allCached(critic))

        # Filter out those cached objects (including this) whose assigned
        # reviewers hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if ReviewableFileChange.fromWrapper(rfc).__reviewed_by is None:
                need_fetch.append(rfc.id)

        reviewer_ids: Dict[int, List[int]] = defaultdict(list)
        all_user_ids = set()

        async with critic.query(
            """SELECT file, uid
                 FROM reviewuserfiles
                WHERE {file=file_ids:array}
                  AND reviewed""",
            file_ids=need_fetch,
        ) as result:
            async for rfc_id, reviewer_id in result:
                reviewer_ids[rfc_id].append(reviewer_id)
                all_user_ids.add(reviewer_id)

        all_users = {
            user.id: user for user in await api.user.fetchMany(critic, all_user_ids)
        }

        for rfc_id in need_fetch:
            ReviewableFileChange.fromWrapper(
                cached_objects[rfc_id]
            ).__reviewed_by = frozenset(
                all_users[reviewer_id] for reviewer_id in reviewer_ids[rfc_id]
            )

    async def getReviewedBy(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.user.User]:
        async with Critic.fromWrapper(critic).criticalSection(REVIEWED_BY):
            if self.__reviewed_by is None:
                await self.__loadReviewedBy(critic)
                assert self.__reviewed_by is not None
        return self.__reviewed_by

    @staticmethod
    async def __loadAssignedReviewers(critic: api.critic.Critic) -> None:
        cached_objects = dict(ReviewableFileChange.allCached(critic))

        # Filter out those cached objects (including this) whose assigned
        # reviewers hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if ReviewableFileChange.fromWrapper(rfc).__assigned_reviewers is None:
                need_fetch.append(rfc.id)

        reviewer_ids: Dict[int, List[int]] = defaultdict(list)
        all_user_ids = set()

        async with critic.query(
            """SELECT file, uid
                 FROM reviewuserfiles
                WHERE {file=file_ids:array}""",
            file_ids=need_fetch,
        ) as result:
            async for rfc_id, reviewer_id in result:
                reviewer_ids[rfc_id].append(reviewer_id)
                all_user_ids.add(reviewer_id)

        all_users = {
            user.id: user for user in await api.user.fetchMany(critic, all_user_ids)
        }

        for rfc_id in need_fetch:
            ReviewableFileChange.fromWrapper(
                cached_objects[rfc_id]
            ).__assigned_reviewers = frozenset(
                all_users[reviewer_id] for reviewer_id in reviewer_ids[rfc_id]
            )

    async def getAssignedReviewers(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.user.User]:
        async with Critic.fromWrapper(critic).criticalSection(ASSIGNED_REVIEWERS):
            if self.__assigned_reviewers is None:
                await self.__loadAssignedReviewers(critic)
                assert self.__assigned_reviewers is not None
        return self.__assigned_reviewers

    @staticmethod
    async def __loadDraftChanges(
        critic: api.critic.Critic, user: api.user.User
    ) -> None:
        cached_objects = dict(ReviewableFileChange.allCached(critic))

        # Filter out those cached objects (including this) whose draft
        # changes hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if not ReviewableFileChange.fromWrapper(rfc).__draft_changes_fetched:
                need_fetch.append(rfc.id)

        async with critic.query(
            """SELECT file, to_reviewed
                 FROM reviewfilechanges
                WHERE uid={user}
                  AND state='draft'
                  AND {file=file_ids:array}""",
            user=user,
            file_ids=need_fetch,
        ) as result:
            draft_changes = dict(await result.all())

        for rfc_id in need_fetch:
            rfc = cached_objects[rfc_id]
            ReviewableFileChange.fromWrapper(rfc).__draft_changes_fetched = True
            if rfc_id in draft_changes:
                to_is_reviewed = draft_changes[rfc_id]
                ReviewableFileChange.fromWrapper(rfc).__draft_changes = DraftChanges(
                    user, to_is_reviewed
                )

    async def getDraftChanges(
        self, critic: api.critic.Critic
    ) -> Optional[WrapperType.DraftChanges]:
        user = critic.effective_user

        # Anonymous (or system) users can't have draft changes.
        if user.type != "regular":
            return None

        async with Critic.fromWrapper(critic).criticalSection(DRAFT_CHANGES):
            if not self.__draft_changes_fetched:
                await self.__loadDraftChanges(critic, user)
                assert self.__draft_changes_fetched
        return self.__draft_changes

    @classmethod
    def refresh_tables(cls) -> Set[str]:
        return {"reviewfiles", "reviewfilechanges", "reviewuserfiles"}


@public.fetchImpl
@ReviewableFileChange.cached
async def fetch(critic: api.critic.Critic, filechange_id: int) -> WrapperType:
    async with ReviewableFileChange.query(
        critic,
        f"""SELECT {ReviewableFileChange.columns()}
              FROM {ReviewableFileChange.table()}
             WHERE id={{filechange_id}}""",
        filechange_id=filechange_id,
    ) as result:
        return await ReviewableFileChange.makeOne(critic, result)


@public.fetchManyImpl
@ReviewableFileChange.cachedMany
async def fetchMany(
    critic: api.critic.Critic, filechange_ids: Iterable[int]
) -> Sequence[WrapperType]:
    async with ReviewableFileChange.query(
        critic,
        ["id=ANY ({filechange_ids})"],
        filechange_ids=filechange_ids,
    ) as result:
        return await ReviewableFileChange.make(critic, result)


@public.fetchAllImpl
async def fetchAll(
    review: api.review.Review,
    changeset: Optional[api.changeset.Changeset],
    file: Optional[api.file.File],
    assignee: Optional[api.user.User],
    is_reviewed: Optional[bool],
) -> Sequence[WrapperType]:
    critic = review.critic
    joins = [ReviewableFileChange.table()]
    conditions = ["reviewfiles.review={review}"]
    if changeset:
        if file is None and assignee is None and is_reviewed is None:
            per_changeset = ReviewableFileChange.get_cached_custom(critic, review)
            if per_changeset is not None and changeset.id in per_changeset:
                return per_changeset[changeset.id]

        # Check if the changeset is a "squash" of the changes in multiple
        # commits. If so, return the reviewable file changes from each of the
        # commits.
        contributing_commits = await changeset.contributing_commits
        if contributing_commits is None:
            raise api.reviewablefilechange.InvalidChangeset(changeset)
        if len(contributing_commits) > 1:
            contributed_rfcs: List[WrapperType] = []
            try:
                for commit in contributing_commits:
                    # Note: Checking that it is a reviewable commit here is sort
                    # of redundant; we could just call fetchAll() recursively,
                    # and it would raise an InvalidChangeset if it is not. The
                    # problem is that if it is not a reviewable commit, there
                    # may not be a changeset prepared for it, which would make
                    # this asynchronous. As long as we only deal with reviewable
                    # commits, the api.changeset.fetch() call is guaranteed to
                    # succeed synchronously.
                    if not await review.isReviewableCommit(commit):
                        raise api.reviewablefilechange.InvalidChangeset(changeset)
                    commit_changeset = await api.changeset.fetch(
                        critic, single_commit=commit
                    )
                    contributed_rfcs.extend(
                        await fetchAll(
                            review, commit_changeset, file, assignee, is_reviewed
                        )
                    )
            except api.reviewablefilechange.InvalidChangeset:
                raise api.reviewablefilechange.InvalidChangeset(changeset)
            return sorted(contributed_rfcs, key=lambda change: change.id)
        else:
            (commit,) = contributing_commits
            if not await review.isReviewableCommit(commit):
                raise api.reviewablefilechange.InvalidChangeset(changeset)
        conditions.append("reviewfiles.changeset={changeset}")
    if file:
        conditions.append("reviewfiles.file={file}")
    if assignee:
        joins.append(
            """JOIN reviewuserfiles ON (
                 reviewuserfiles.file=reviewfiles.id
               )"""
        )
        conditions.append("reviewuserfiles.uid={assignee}")
    if is_reviewed is not None:
        if assignee:
            # If the specified assignee has a draft change to the state, use
            # that changed state instead of the actual state when filtering.
            joins.append(
                """
                LEFT OUTER JOIN reviewfilechanges ON (
                    reviewfilechanges.file=reviewuserfiles.file AND
                    reviewfilechanges.uid=reviewuserfiles.uid AND
                    reviewfilechanges.state='draft'
                )
            """
            )
            conditions.append(
                """
                COALESCE(
                    reviewfilechanges.to_reviewed,
                    reviewuserfiles.reviewed
                )={is_reviewed}
            """
            )
        else:
            conditions.append("reviewfiles.reviewed={is_reviewed}")

    async with ReviewableFileChange.query(
        critic,
        f"""SELECT {ReviewableFileChange.columns()}
              FROM {" ".join(joins)}
             WHERE {" AND ".join(conditions)}
          ORDER BY id""",
        review=review,
        changeset=changeset,
        file=file,
        assignee=assignee,
        is_reviewed=is_reviewed,
    ) as result:
        rfcs = await ReviewableFileChange.make(critic, result)

    if file is None and assignee is None and is_reviewed is None:
        per_changeset = ReviewableFileChange.get_cached_custom(
            critic, review, defaultdict(list)
        )
        for rfc in rfcs:
            per_changeset[ReviewableFileChange.fromWrapper(rfc).changeset_id].append(
                rfc
            )
        ReviewableFileChange.set_cached_custom(critic, review, per_changeset)

    return rfcs
