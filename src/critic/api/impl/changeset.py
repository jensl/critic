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
import logging
from typing import Tuple, Sequence, Optional, FrozenSet, Set, Union, Iterable, List

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api
from ...syntaxhighlight.ranges import SyntaxHighlightRanges


WrapperType = api.changeset.Changeset
ArgumentsType = Tuple[int, bool, bool, int, int, int]


class Changeset(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.changeset.Changeset
    column_names = [
        "id",
        "complete",
        "is_replay",
        "repository",
        "from_commit",
        "to_commit",
    ]

    __is_direct: Optional[bool]

    def __init__(self, args: ArgumentsType) -> None:
        (
            self.id,
            self.is_complete,
            self.is_replay,
            self.__repository_id,
            self.__from_commit_id,
            self.__to_commit_id,
        ) = args
        self.__is_direct = None

    def set_is_direct(self, value: bool) -> None:
        self.__is_direct = value

    async def isDirect(self, critic: api.critic.Critic) -> bool:
        if self.__is_direct is None:
            from_commit = await self.getFromCommit(critic)
            to_commit = await self.getToCommit(critic)
            self.__is_direct = (
                from_commit is not None
                and from_commit.sha1 in to_commit.low_level.parents
            )
        return self.__is_direct

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await api.repository.fetch(critic, self.__repository_id)

    async def getFromCommit(
        self, critic: api.critic.Critic
    ) -> Optional[api.commit.Commit]:
        if self.__from_commit_id is None:
            return None
        return await api.commit.fetch(
            await self.getRepository(critic), self.__from_commit_id
        )

    async def getToCommit(self, critic: api.critic.Critic) -> api.commit.Commit:
        return await api.commit.fetch(
            await self.getRepository(critic), self.__to_commit_id
        )

    async def getContributingCommits(
        self, critic: api.critic.Critic
    ) -> Optional[api.commitset.CommitSet]:
        try:
            return await api.commitset.calculateFromRange(
                critic, await self.getFromCommit(critic), await self.getToCommit(critic)
            )
        except api.commitset.InvalidCommitRange:
            return None

    async def getCompletionLevel(
        self,
        wrapper: WrapperType,
        wanted_levels: Set[api.changeset.CompletionLevel] = set(),
    ) -> Union[bool, FrozenSet[api.changeset.CompletionLevel]]:
        critic = wrapper.critic
        level: Set[api.changeset.CompletionLevel] = set()

        def want_level(level: api.changeset.CompletionLevel) -> bool:
            return not wanted_levels or bool(wanted_levels & {level, "full"})

        def wanted_reached() -> bool:
            return bool(wanted_levels) and wanted_levels.issubset(level)

        def return_value() -> Union[bool, FrozenSet[api.changeset.CompletionLevel]]:
            if wanted_levels:
                return wanted_levels.issubset(level)
            return frozenset(level)

        if not self.is_complete:
            return return_value()

        level.add("structure")

        if wanted_reached():
            return return_value()

        async with api.critic.Query[bool](
            wrapper.critic,
            """SELECT complete
                 FROM changesetcontentdifferences
                WHERE changeset={changeset_id}""",
            changeset_id=self.id,
        ) as result:
            try:
                content_complete = await result.scalar()
            except result.ZeroRowsInResult:
                content_complete = False

        if not content_complete:
            return return_value()

        level.add("changedlines")

        if wanted_reached():
            return return_value()

        if want_level("analysis") or want_level("syntaxhighlight"):
            async with wrapper.critic.query(
                """SELECT 1
                     FROM changesetchangedlines
                    WHERE changeset={changeset_id}
                      AND analysis IS NULL
                    LIMIT 1""",
                changeset_id=self.id,
            ) as result:
                if await result.empty():
                    level.add("analysis")

            if wanted_reached():
                return return_value()

        if "analysis" in level and want_level("syntaxhighlight"):
            repository = await wrapper.repository
            filediffs = await api.filediff.fetchAll(wrapper)

            async with SyntaxHighlightRanges.make(repository) as ranges:
                for filediff in filediffs:
                    if filediff.old_syntax is not None:
                        ranges.add_file_version(
                            filediff.filechange.old_sha1,
                            filediff.old_syntax,
                            self.is_replay,
                        )
                    if filediff.new_syntax is not None:
                        ranges.add_file_version(
                            filediff.filechange.new_sha1, filediff.new_syntax, False
                        )
                await ranges.fetch()

            for file_version in ranges.file_versions:
                if not file_version.is_highlighted:
                    break
            else:
                level.add("syntaxhighlight")

            if wanted_reached():
                return return_value()

        if {"analysis", "syntaxhighlight"}.issubset(level):
            level.add("full")

        return return_value()

    async def ensure(
        self,
        wrapper: WrapperType,
        completion_levels: Set[api.changeset.CompletionLevel],
        block: bool,
    ) -> bool:
        critic = wrapper.critic

        async def refresh() -> Changeset:
            await self.refresh(critic, {"changesets"}, {self.id: wrapper})
            return wrapper._impl

        iterations = 1

        while True:
            self = await refresh()

            if await self.getCompletionLevel(wrapper, completion_levels):
                return True

            if not block:
                return False

            await asyncio.sleep(min(60, iterations * 0.2), loop=critic.loop)
            iterations += 1


@Changeset.cached
async def fetch(
    critic: api.critic.Critic,
    changeset_id: Optional[int],
    from_commit: Optional[api.commit.Commit],
    to_commit: Optional[api.commit.Commit],
    single_commit: Optional[api.commit.Commit],
    conflicts: bool,
) -> WrapperType:
    if changeset_id is None:
        if to_commit:
            return await get_changeset(critic, from_commit, to_commit, conflicts)
        elif single_commit:
            parents = await single_commit.parents
            parent = parents[0] if parents else None
            return await get_changeset(critic, parent, single_commit)

    async with Changeset.query(
        critic, ["id={changeset_id}"], changeset_id=changeset_id
    ) as result:
        try:
            changeset = await Changeset.makeOne(critic, result)
        except result.ZeroRowsInResult:
            raise api.changeset.InvalidId(invalid_id=changeset_id)

    changeset._impl.set_is_direct(
        single_commit is not None
        or (from_commit and to_commit and from_commit in to_commit.low_level.parents)
    )

    return changeset


async def fetchAutomatic(
    review: api.review.Review, automatic: api.changeset.AutomaticMode
) -> WrapperType:
    async def full_changeset() -> WrapperType:
        branch = await review.branch
        if branch:
            commits = await branch.commits
        else:
            commits = await review.commits
        upstreams = await commits.filtered_tails

        if len(upstreams) != 1:
            raise api.changeset.Error(
                "Automatic mode failed: not a single upstream commit"
            )

        (upstream,) = upstreams
        (head,) = commits.heads

        return await api.changeset.fetch(
            review.critic, from_commit=upstream, to_commit=head
        )

    if automatic == "everything":
        return await full_changeset()

    # Legacy code no longer works. Must be rewritten.
    raise api.changeset.Error("Automatic mode failed")

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
    #     raise api.changeset.Error("Automatic mode failed")
    # except page_showcommit.NoChangesFound:
    #     assert automatic != "everything"
    #     raise api.changeset.AutomaticChangesetEmpty("No %s changes found"
    #                                                 % automatic)

    # from_commit = await api.commit.fetch(repository, sha1=from_sha1)
    # to_commit = await api.commit.fetch(repository, sha1=to_sha1)

    # if from_commit == to_commit:
    #     single_commit = to_commit
    #     from_commit = to_commit = None
    # else:
    #     single_commit = None

    # return await fetch(critic, None, from_commit, to_commit, single_commit)


async def fetchMany(
    critic: api.critic.Critic,
    changeset_ids: Optional[Iterable[int]],
    branchupdate: Optional[api.branchupdate.BranchUpdate],
) -> List[WrapperType]:
    if changeset_ids is not None:
        async with Changeset.query(
            critic, ["id=ANY ({changeset_ids})"], changeset_ids=list(changeset_ids)
        ) as result:
            return await Changeset.make(critic, result)
    else:
        async with Changeset.query(
            critic,
            f"""SELECT {Changeset.columns()}
                  FROM {Changeset.table()}
                  JOIN reviewchangesets ON (changeset=id)
                 WHERE branchupdate={{branchupdate}}
              ORDER BY id""",
            branchupdate=branchupdate,
        ) as result:
            return await Changeset.make(critic, result)


async def get_changeset(
    critic: api.critic.Critic,
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    conflicts: bool = False,
) -> api.changeset.Changeset:
    async with api.transaction.start(critic) as transaction:
        changeset = await transaction.ensureChangeset(
            from_commit, to_commit, conflicts=conflicts
        )
        changeset.requestContent().requestHighlight()

    return await changeset
