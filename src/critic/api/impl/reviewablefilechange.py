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
from typing import (
    Callable,
    Tuple,
    Optional,
    Iterable,
    Sequence,
    Dict,
    List,
    Collection,
    Set,
    cast,
)

from critic.api.impl.queryhelper import QueryHelper, QueryResult, join, left_outer_join

logger = logging.getLogger(__name__)

from critic import api
from critic.api import reviewablefilechange as public
from .apiobject import APIObjectImplWithId

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


PublicType = public.ReviewableFileChange
ArgumentsType = Tuple[int, int, int, int, int, int, int, bool]


class ReviewableFileChange(PublicType, APIObjectImplWithId, module=public):
    __reviewed_by: Optional[Collection[api.user.User]]
    __assigned_reviewers: Optional[Collection[api.user.User]]
    __draft_changes: Optional[PublicType.DraftChanges]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__review_id,
            self.__changeset_id,
            self.__file_id,
            self.__scope_id,
            self.__inserted_lines,
            self.__deleted_lines,
            self.__is_reviewed,
        ) = args

        self.__reviewed_by = None
        self.__assigned_reviewers = None
        self.__draft_changes = None
        self.__draft_changes_fetched = False
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def changeset_id(self) -> int:
        return self.__changeset_id

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def changeset(self) -> api.changeset.Changeset:
        return await api.changeset.fetch(self.critic, self.__changeset_id)

    @property
    async def file(self) -> api.file.File:
        return await api.file.fetch(self.critic, self.__file_id)

    @property
    async def scope(self) -> Optional[api.reviewscope.ReviewScope]:
        if self.__scope_id is None:
            return None
        return await api.reviewscope.fetch(self.critic, self.__scope_id)

    @property
    def deleted_lines(self) -> int:
        return self.__deleted_lines

    @property
    def inserted_lines(self) -> int:
        return self.__inserted_lines

    @property
    def is_reviewed(self) -> bool:
        return self.__is_reviewed

    async def __loadReviewedBy(self, critic: api.critic.Critic) -> None:
        cached_objects = ReviewableFileChange.allCached()

        # Filter out those cached objects (including this) whose assigned
        # reviewers hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if rfc.__reviewed_by is None:
                need_fetch.append(rfc.id)

        reviewer_ids: Dict[int, List[int]] = defaultdict(list)
        all_user_ids = set()

        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT file, uid
                 FROM reviewuserfiles
                WHERE file=ANY({file_ids})
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
            cached_objects[rfc_id].__reviewed_by = frozenset(
                all_users[reviewer_id] for reviewer_id in reviewer_ids[rfc_id]
            )

    @property
    async def reviewed_by(self) -> Collection[api.user.User]:
        if self.__reviewed_by is None:
            await self.__loadReviewedBy(self.critic)
            assert self.__reviewed_by is not None
        return self.__reviewed_by

    @staticmethod
    async def __loadAssignedReviewers(critic: api.critic.Critic) -> None:
        cached_objects = ReviewableFileChange.allCached()

        # Filter out those cached objects (including this) whose assigned
        # reviewers hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if rfc.__assigned_reviewers is None:
                need_fetch.append(rfc.id)

        reviewer_ids: Dict[int, List[int]] = defaultdict(list)
        all_user_ids = set()

        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT file, uid
                 FROM reviewuserfiles
                WHERE file=ANY({file_ids})""",
            file_ids=need_fetch,
        ) as result:
            async for rfc_id, reviewer_id in result:
                reviewer_ids[rfc_id].append(reviewer_id)
                all_user_ids.add(reviewer_id)

        all_users = {
            user.id: user for user in await api.user.fetchMany(critic, all_user_ids)
        }

        for rfc_id in need_fetch:
            cached_objects[rfc_id].__assigned_reviewers = frozenset(
                all_users[reviewer_id] for reviewer_id in reviewer_ids[rfc_id]
            )

    @property
    async def assigned_reviewers(self) -> Collection[api.user.User]:
        if self.__assigned_reviewers is None:
            await self.__loadAssignedReviewers(self.critic)
            assert self.__assigned_reviewers is not None
        return self.__assigned_reviewers

    @staticmethod
    async def __loadDraftChanges(
        critic: api.critic.Critic, user: api.user.User
    ) -> None:
        cached_objects = ReviewableFileChange.allCached()

        # Filter out those cached objects (including this) whose draft
        # changes hasn't been fetched yet.
        need_fetch = []
        for rfc in cached_objects.values():
            if not rfc.__draft_changes_fetched:
                need_fetch.append(rfc.id)

        async with api.critic.Query[Tuple[int, bool]](
            critic,
            """SELECT file, to_reviewed
                 FROM reviewuserfilechanges
                WHERE uid={user}
                  AND state='draft'
                  AND file=ANY({file_ids})""",
            user=user,
            file_ids=need_fetch,
        ) as result:
            draft_changes = dict(await result.all())

        for rfc_id in need_fetch:
            rfc = cached_objects[rfc_id]
            rfc.__draft_changes_fetched = True
            if rfc_id in draft_changes:
                to_is_reviewed = draft_changes[rfc_id]
                rfc.__draft_changes = DraftChanges(user, to_is_reviewed)

    @property
    async def draft_changes(self) -> Optional[PublicType.DraftChanges]:
        user = self.critic.effective_user

        # Anonymous (or system) users can't have draft changes.
        if user.type != "regular":
            return None

        if not self.__draft_changes_fetched:
            await self.__loadDraftChanges(self.critic, user)
            assert self.__draft_changes_fetched
        return self.__draft_changes

    @classmethod
    def refresh_tables(cls) -> Set[str]:
        return {"reviewfiles", "reviewuserfilechanges", "reviewuserfiles"}

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    ReviewableFileChange.getTableName(),
    "id",
    "review",
    "changeset",
    "file",
    "scope",
    "deleted",
    "inserted",
    "reviewed",
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, filechange_id: int) -> PublicType:
    return await ReviewableFileChange.ensureOne(
        filechange_id, queries.idFetcher(critic, ReviewableFileChange)
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, filechange_ids: Iterable[int]
) -> Sequence[PublicType]:
    return await ReviewableFileChange.ensure(
        [*filechange_ids], queries.idsFetcher(critic, ReviewableFileChange)
    )


def getPerChangesetCache(review: api.review.Review) -> Dict[int, Set[PublicType]]:
    PerChangesetCache = Dict[api.review.Review, Dict[int, Set[PublicType]]]
    cache = cast(PerChangesetCache, ReviewableFileChange.getCustomCache())
    return cache.setdefault(review, defaultdict(set))


@public.fetchAllImpl
async def fetchAll(
    review: api.review.Review,
    changeset: Optional[api.changeset.Changeset],
    file: Optional[api.file.File],
    assignee: Optional[api.user.User],
    is_reviewed: Optional[bool],
) -> Sequence[PublicType]:
    critic = review.critic
    joins = []
    conditions = ["reviewfiles.review={review}"]
    if changeset:
        if file is None and assignee is None and is_reviewed is None:
            per_changeset = getPerChangesetCache(review)
            if changeset.id in per_changeset:
                return [*per_changeset[changeset.id]]

        logger.debug(f"{changeset.automatic=}")
        if changeset.automatic:
            assert changeset.automatic.review == review
            if changeset.automatic.mode == "everything":
                return await fetchAll(review, None, file, assignee, is_reviewed)

        # Check if the changeset is a "squash" of the changes in multiple
        # commits. If so, return the reviewable file changes from each of the
        # commits.
        contributing_commits = await changeset.contributing_commits
        if contributing_commits is None:
            raise api.reviewablefilechange.InvalidChangeset(changeset)
        if len(contributing_commits) > 1:
            contributed_rfcs: List[PublicType] = []
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
        joins.append(join(reviewuserfiles=["reviewuserfiles.file=reviewfiles.id"]))
        conditions.append("reviewuserfiles.uid={assignee}")
    if is_reviewed is not None:
        if assignee:
            # If the specified assignee has a draft change to the state, use
            # that changed state instead of the actual state when filtering.
            joins.append(
                left_outer_join(
                    reviewuserfilechanges=[
                        "reviewuserfilechanges.file=reviewuserfiles.file",
                        "reviewuserfilechanges.uid=reviewuserfiles.uid",
                        "reviewuserfilechanges.state='draft'",
                    ]
                )
            )
            conditions.append(
                """
                COALESCE(
                    reviewuserfilechanges.to_reviewed,
                    reviewuserfiles.reviewed
                )={is_reviewed}
                """
            )
        else:
            conditions.append("reviewfiles.reviewed={is_reviewed}")

    rfcs = ReviewableFileChange.store(
        await queries.query(
            critic,
            queries.formatQuery(*conditions, joins=joins),
            review=review,
            changeset=changeset,
            file=file,
            assignee=assignee,
            is_reviewed=is_reviewed,
        ).make(ReviewableFileChange)
    )

    if file is None and assignee is None and is_reviewed is None:
        per_changeset = getPerChangesetCache(review)
        for rfc in rfcs:
            per_changeset[rfc.changeset_id].add(rfc)

    return rfcs
