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

import asyncio
from dataclasses import dataclass
import logging
from typing import (
    Awaitable,
    Callable,
    Collection,
    Sequence,
    Tuple,
    Optional,
    FrozenSet,
    Set,
    Iterable,
    cast,
)

from critic.api.review import Review


logger = logging.getLogger(__name__)

from critic import api
from critic.api import changeset as public
from critic.syntaxhighlight.ranges import SyntaxHighlightRanges
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult, join


PublicType = public.Changeset
ArgumentsType = Tuple[int, bool, bool, int, int, int]


@dataclass
class Progress:
    __analysis: float
    __syntax_highlight: float

    @property
    def analysis(self) -> float:
        return self.__analysis

    @property
    def syntax_highlight(self) -> float:
        return self.__syntax_highlight


@dataclass
class CompletionLevelResult:
    wanted_level_reached: bool
    completion_level: Collection[public.CompletionLevel]
    progress: Optional[Progress]


@dataclass
class Automatic:
    __review: api.review.Review
    __mode: public.AutomaticMode

    @property
    def review(self) -> api.review.Review:
        return self.__review

    @property
    def mode(self) -> public.AutomaticMode:
        return self.__mode


class Changeset(PublicType, APIObjectImplWithId, module=public):
    __is_direct: Optional[bool]
    __automatic: Optional[Tuple[api.review.Review, public.AutomaticMode]] = None
    __completion_level_result: Optional[CompletionLevelResult]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__is_complete,
            self.__is_replay,
            self.__repository_id,
            self.__from_commit_id,
            self.__to_commit_id,
        ) = args
        self.__is_direct = None
        self.__completion_level_result = None
        return self.__id

    def set_is_direct(self, value: bool) -> None:
        self.__is_direct = value

    def set_automatic(
        self, review: api.review.Review, mode: public.AutomaticMode
    ) -> None:
        self.__automatic = (review, mode)

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def repository(self) -> api.repository.Repository:
        return await api.repository.fetch(self.critic, self.__repository_id)

    @property
    async def from_commit(self) -> Optional[api.commit.Commit]:
        if self.__from_commit_id is None:
            return None
        return await api.commit.fetch(await self.repository, self.__from_commit_id)

    @property
    async def to_commit(self) -> api.commit.Commit:
        return await api.commit.fetch(await self.repository, self.__to_commit_id)

    @property
    async def is_direct(self) -> bool:
        if self.__is_direct is None:
            from_commit = await self.from_commit
            to_commit = await self.to_commit
            self.__is_direct = (
                from_commit is not None
                and from_commit.sha1 in to_commit.low_level.parents
            )
        return self.__is_direct

    @property
    def is_complete(self) -> bool:
        return self.__is_complete

    @property
    def is_replay(self) -> bool:
        return self.__is_replay

    @property
    async def contributing_commits(self) -> Optional[api.commitset.CommitSet]:
        try:
            return await api.commitset.calculateFromRange(
                self.critic, await self.from_commit, await self.to_commit
            )
        except api.commitset.InvalidCommitRange:
            return None

    async def __calculateCompletionLevel(
        self,
        wanted_levels: FrozenSet[public.CompletionLevel] = frozenset(),
    ) -> CompletionLevelResult:
        level: Set[public.CompletionLevel] = set()

        def want_level(level: public.CompletionLevel) -> bool:
            return not wanted_levels or bool(
                wanted_levels.intersection({level, "full"})
            )

        def wanted_reached() -> bool:
            return bool(wanted_levels) and wanted_levels.issubset(level)

        def return_value(progress: Optional[Progress] = None) -> CompletionLevelResult:
            return CompletionLevelResult(wanted_levels.issubset(level), level, progress)

        async with api.critic.Query[bool](
            self.critic,
            """SELECT complete
                 FROM changesets
                WHERE id={changeset_id}""",
            changeset_id=self.id,
        ) as structure_complete_result:
            if not await structure_complete_result.scalar():
                return return_value()

        level.add("structure")

        if wanted_reached():
            return return_value()

        async with api.critic.Query[bool](
            self.critic,
            """SELECT complete
                 FROM changesetcontentdifferences
                WHERE changeset={changeset_id}""",
            changeset_id=self.id,
        ) as content_complete_result:
            try:
                content_complete = await content_complete_result.scalar()
            except content_complete_result.ZeroRowsInResult:
                content_complete = False

        if not content_complete:
            return return_value()

        level.add("changedlines")

        if wanted_reached():
            return return_value()

        analysis_done = 0
        analysis_total = 0

        if want_level("analysis"):
            async with api.critic.Query[Tuple[bool, int]](
                self.critic,
                """SELECT is_analyzed, COUNT(*)
                     FROM (
                       SELECT analysis IS NOT NULL AS is_analyzed, "file", "index"
                         FROM changesetchangedlines
                        WHERE changeset={changeset_id}
                     ) AS intermediate
                 GROUP BY is_analyzed""",
                changeset_id=self.id,
            ) as analysis_result:
                anaysis_remaining = 0
                rows = await analysis_result.all()
                logger.debug(f"{rows=}")
                for is_analyzed, count in rows:
                    if is_analyzed:
                        analysis_done = count
                    else:
                        anaysis_remaining = count
                if anaysis_remaining == 0:
                    level.add("analysis")
                analysis_total = analysis_done + anaysis_remaining

            if wanted_reached():
                return return_value()

        highlight_done = 0
        highlight_total = 0

        if want_level("syntaxhighlight"):
            repository = await self.repository
            filediffs = await api.filediff.fetchAll(self)

            async with SyntaxHighlightRanges.make(repository) as ranges:
                for filediff in filediffs:
                    if filediff.old_syntax is not None:
                        assert filediff.filechange.old_sha1
                        ranges.add_file_version(
                            filediff.filechange.old_sha1,
                            filediff.old_syntax,
                            self.is_replay,
                        )
                    if filediff.new_syntax is not None:
                        assert filediff.filechange.new_sha1
                        ranges.add_file_version(
                            filediff.filechange.new_sha1, filediff.new_syntax, False
                        )
                await ranges.fetch()

            highlight_total = len(ranges.file_versions)
            highlight_done = sum(
                int(file_version.is_highlighted)
                for file_version in ranges.file_versions
            )

            if highlight_done == highlight_total:
                level.add("syntaxhighlight")

            if wanted_reached():
                return return_value()

        if {"analysis", "syntaxhighlight"}.issubset(level):
            level.add("full")

        return return_value(
            Progress(
                float(analysis_done) / analysis_total if analysis_total != 0 else 0,
                float(highlight_done) / highlight_total if highlight_total != 0 else 0,
            )
        )

    @property
    async def completion_level(self) -> Collection[public.CompletionLevel]:
        if self.__completion_level_result is None:
            self.__completion_level_result = await self.__calculateCompletionLevel()
        return self.__completion_level_result.completion_level

    @property
    async def progress(self) -> Optional[public.Progress]:
        if self.__completion_level_result is None:
            self.__completion_level_result = await self.__calculateCompletionLevel()
        return self.__completion_level_result.progress

    async def ensure_completion_level(
        self, *completion_levels: public.CompletionLevel, block: bool = True
    ) -> bool:
        if not completion_levels:
            completion_levels = ("full",)
        wanted_levels = frozenset(completion_levels)
        iterations = 1

        while True:
            result = await self.__calculateCompletionLevel(wanted_levels)

            if result.wanted_level_reached:
                if iterations > 1:
                    await self.refresh()
                return True

            if not block:
                return False

            await asyncio.sleep(min(60, iterations * 0.2))
            iterations += 1

    @property
    def automatic(self) -> Optional[PublicType.Automatic]:
        if self.__automatic is None:
            return None
        review, mode = self.__automatic
        return Automatic(review, mode)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "complete",
    "is_replay",
    "repository",
    "from_commit",
    "to_commit",
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    changeset_id: Optional[int],
    from_commit: Optional[api.commit.Commit],
    to_commit: Optional[api.commit.Commit],
    single_commit: Optional[api.commit.Commit],
    conflicts: bool,
) -> PublicType:
    if changeset_id is not None:
        return await Changeset.ensureOne(
            changeset_id, queries.idFetcher(critic, Changeset)
        )
    if to_commit is not None:
        return await get_changeset(critic, from_commit, to_commit, conflicts)
    assert single_commit is not None
    parents = await single_commit.parents
    parent = parents[0] if parents else None
    return await get_changeset(critic, parent, single_commit)


@public.fetchAutomaticImpl
async def fetchAutomatic(
    review: api.review.Review, mode: public.AutomaticMode
) -> PublicType:
    user = review.critic.effective_user

    async def full_changeset() -> PublicType:
        branch = await review.branch
        if branch:
            commits = await branch.commits
        else:
            commits = await review.commits
        upstreams = await commits.filtered_tails

        if len(upstreams) != 1:
            raise public.Error("Automatic mode failed: not a single upstream commit")

        (upstream,) = upstreams
        (head,) = commits.heads

        return await public.fetch(review.critic, from_commit=upstream, to_commit=head)

    async def filtered_changeset(
        rfcs: Sequence[api.reviewablefilechange.ReviewableFileChange],
        include: Callable[
            [api.reviewablefilechange.ReviewableFileChange], Awaitable[bool]
        ],
    ) -> PublicType:
        included_commits: Set[api.commit.Commit] = set()

        for rfc in rfcs:
            if not await include(rfc):
                continue

            changeset = await rfc.changeset
            included_commits.add(await changeset.to_commit)

        logger.debug(f"{included_commits=}")

        if not included_commits:
            raise public.AutomaticChangesetEmpty("No changes found")

        first_commit: Optional[api.commit.Commit] = None
        last_commit: Optional[api.commit.Commit] = None

        partition = await review.first_partition
        while partition:
            for commit in partition.commits.topo_ordered:
                if commit not in included_commits:
                    continue

                included_commits.remove(commit)
                if last_commit is None:
                    last_commit = commit
                first_commit = commit

            logger.debug(f"{first_commit=} {last_commit=}")

            if first_commit and last_commit:
                if included_commits:
                    raise public.AutomaticChangesetImpossible("Review has been rebased")
                if first_commit.is_merge:
                    raise public.AutomaticChangesetImpossible("First commit is a merge")
                return await public.fetch(
                    review.critic,
                    from_commit=(await first_commit.parents)[0],
                    to_commit=last_commit,
                )

            if not partition.following:
                break
            partition = partition.following.partition

        raise public.Error("Automatic mode failed")

    async def is_pending(rfc: api.reviewablefilechange.ReviewableFileChange) -> bool:
        return not rfc.is_reviewed

    async def is_unseen(rfc: api.reviewablefilechange.ReviewableFileChange) -> bool:
        return user in await rfc.reviewed_by

    if mode == "everything":
        changeset = await full_changeset()
    elif mode == "pending":
        changeset = await filtered_changeset(
            await api.reviewablefilechange.fetchAll(review, is_reviewed=False),
            is_pending,
        )
    elif mode == "unseen":
        if not user.is_regular:
            raise public.AutomaticChangesetImpossible("Must be signed in")
        changeset = await filtered_changeset(
            await api.reviewablefilechange.fetchAll(
                review, is_reviewed=False, assignee=user
            ),
            is_unseen,
        )
    else:
        # Legacy code no longer works. Must be rewritten.
        raise public.Error("Automatic mode failed")

    cast(Changeset, changeset).set_automatic(review, mode)
    return changeset

    # Handle automatic changesets using legacy code.
    # from critic import dbutils
    # from ...wsgi import request
    # from ...page import showcommit as page_showcommit

    # critic = review.critic
    # repository = review.repository

    # legacy_user = dbutils.User.fromAPI(critic.effective_user)
    # legacy_review = dbutils.Review.fromAPI(review)

    # try:
    #     from_sha1, to_sha1, all_commits, listed_commits = \
    #         page_showcommit.commitRangeFromReview(
    #             critic.database, legacy_user, legacy_review, automatic, [])
    # except request.DisplayMessage:
    #     # FIXME: This error message could be better. The legacy code does
    #     # report more useful error messages, but does it in a way that's
    #     # pretty tied to the old HTML UI. Some refactoring is needed.
    #     raise public.Error("Automatic mode failed")
    # except page_showcommit.NoChangesFound:
    #     assert automatic != "everything"
    #     raise public.AutomaticChangesetEmpty("No %s changes found"
    #                                                 % automatic)

    # from_commit = await api.commit.fetch(repository, sha1=from_sha1)
    # to_commit = await api.commit.fetch(repository, sha1=to_sha1)

    # if from_commit == to_commit:
    #     single_commit = to_commit
    #     from_commit = to_commit = None
    # else:
    #     single_commit = None

    # return await fetch(critic, None, from_commit, to_commit, single_commit)


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic,
    changeset_ids: Optional[Iterable[int]],
    branchupdate: Optional[api.branchupdate.BranchUpdate],
) -> Sequence[PublicType]:
    if changeset_ids is not None:
        return await Changeset.ensure(
            [*changeset_ids], queries.idsFetcher(critic, Changeset)
        )
    return Changeset.store(
        await queries.query(
            critic,
            queries.formatQuery(
                "rcs.branchupdate={branchupdate}",
                joins=[
                    join(reviewchangesets=["reviewchangesets.changeset=changesets.id"])
                ],
            ),
            branchupdate=branchupdate,
        ).make(Changeset)
    )


async def get_changeset(
    critic: api.critic.Critic,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    conflicts: bool = False,
) -> public.Changeset:
    async with api.transaction.start(critic) as transaction:
        modifier = await transaction.ensureChangeset(
            from_commit, to_commit, conflicts=conflicts
        )
        await modifier.requestContent()
        await modifier.requestHighlight()
        return modifier.subject
