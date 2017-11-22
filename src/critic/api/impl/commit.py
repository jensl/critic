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
import re
import logging
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple, Optional, Union, cast

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api
from critic import diff
from critic import gitaccess
from critic.gitaccess import SHA1

RE_FOLLOWUP = re.compile("(fixup|squash)!.*(?:\n[ \t]*)+(.*)")


@dataclass(frozen=True)
class UserAndTimestamp:
    name: str
    email: str
    timestamp: datetime.datetime


@dataclass(frozen=True)
class FileInformation:
    file: api.file.File
    mode: int
    sha1: SHA1
    size: int


WrapperType = api.commit.Commit
ArgumentsType = Tuple[api.repository.Repository, int, gitaccess.GitObject]
CacheKeyType = Tuple[int, Union[int, SHA1]]


class Commit(apiobject.APIObject[WrapperType, ArgumentsType, CacheKeyType]):
    wrapper_class = WrapperType

    def __init__(self, args: ArgumentsType):
        (self.repository, self.id, low_level) = args
        self.low_level = low_level.asCommit()
        self.sha1 = self.low_level.sha1
        self.tree = self.low_level.tree

    def getSummary(self) -> str:
        match = RE_FOLLOWUP.match(self.low_level.message)
        if match:
            followup_type, summary = match.groups()
            return "[%s] %s" % (followup_type, summary)
        return self.low_level.message.split("\n", 1)[0]

    def isMerge(self) -> bool:
        return len(self.low_level.parents) > 1

    async def getParents(self) -> Tuple[WrapperType, ...]:
        if not self.low_level.parents:
            return ()
        return tuple(
            await fetchMany(self.repository, None, self.low_level.parents, None)
        )

    async def getDescription(
        self, wrapper: WrapperType
    ) -> api.commit.CommitDescription:
        return await CommitDescription.makeOne(wrapper.critic, wrapper)

    def getAuthor(self, critic: api.critic.Critic) -> WrapperType.UserAndTimestamp:
        return UserAndTimestamp(
            self.low_level.author.name,
            self.low_level.author.email,
            self.low_level.author.time,
        )

    def getCommitter(self, critic: api.critic.Critic) -> WrapperType.UserAndTimestamp:
        return UserAndTimestamp(
            self.low_level.committer.name,
            self.low_level.committer.email,
            self.low_level.committer.time,
        )

    def isParentOf(self, child: WrapperType) -> bool:
        return self.low_level.sha1 in child.low_level.parents

    async def isAncestorOf(self, commit: WrapperType) -> bool:
        return await self.repository.low_level.mergebase(
            self.sha1, commit.sha1, is_ancestor=True
        )

    async def getFileInformation(
        self, file: api.file.File
    ) -> Optional[WrapperType.FileInformation]:
        entries = await self.repository.low_level.lstree(
            self.sha1, file.path, long_format=True
        )
        if not entries:
            return None
        entry = entries[0]
        if len(entries) > 1 or entry.object_type != "blob" or not entry.isreg():
            raise api.commit.NotAFile(file.path)
        assert entry.size is not None, entry
        return FileInformation(file, entry.mode, entry.sha1, entry.size)

    async def getFileContents(self, file: api.file.File) -> Optional[bytes]:
        information = await self.getFileInformation(file)
        if information is None:
            return None
        return cast(
            gitaccess.GitBlob,
            await self.repository.low_level.fetchone(
                information.sha1, wanted_object_type="blob"
            ),
        ).data

    async def getFileLines(self, file: api.file.File) -> Optional[Sequence[str]]:
        contents = await self.getFileContents(file)
        if contents is None:
            return None
        return diff.parse.splitlines(contents)

    @staticmethod
    def create(critic: api.critic.Critic, args: ArgumentsType) -> WrapperType:
        repository_id = int(args[0])
        wrapper = Commit(args).wrap(critic)
        Commit.add_cached(critic, (repository_id, wrapper.id), wrapper)
        Commit.add_cached(critic, (repository_id, wrapper.sha1), wrapper)
        return wrapper


class CommitDescription(
    apiobject.APIObject[
        api.commit.CommitDescription, api.commit.Commit, api.commit.Commit
    ]
):
    wrapper_class = api.commit.CommitDescription

    __branch: Optional[api.branch.Branch]
    __branch_calculated: bool

    def __init__(self, commit: api.commit.Commit) -> None:
        self.commit = commit
        self.__branch = None
        self.__branch_calculated = False

    async def __calculateBranch(
        self, critic: api.critic.Critic
    ) -> Optional[api.branch.Branch]:
        async with api.critic.Query[int](
            critic,
            """SELECT branchcommits.branch
                 FROM branchcommits
                 JOIN branchupdates ON (
                        branchupdates.branch=branchcommits.branch
                      )
                 JOIN branchupdatecommits ON (
                        branchupdatecommits.branchupdate=branchupdates.id
                      )
                WHERE branchcommits.commit={commit}
             ORDER BY branchupdates.id DESC
                LIMIT 1""",
            commit=self.commit,
        ) as result:
            try:
                branch_id = await result.scalar()
            except result.ZeroRowsInResult:
                return None

        return await api.branch.fetch(critic, branch_id)

    async def getBranch(self, critic: api.critic.Critic) -> Optional[api.branch.Branch]:
        if not self.__branch_calculated:
            self.__branch = await self.__calculateBranch(critic)
            self.__branch_calculated = True
        return self.__branch

    # async def getTag(self, critic: api.critic.Critic):
    #     # FIXME: Support tags.
    #     return None

    @staticmethod
    def cacheKey(wrapper: api.commit.CommitDescription) -> api.commit.Commit:
        return wrapper.commit


async def fetch(
    repository: api.repository.Repository,
    commit_id: Optional[int],
    sha1: Optional[SHA1],
    ref: Optional[str],
) -> WrapperType:
    critic = repository.critic
    repository_id = int(repository)

    async def commit_id_from_sha1() -> int:
        assert sha1
        async with api.critic.Query[int](
            critic,
            """SELECT id
                 FROM commits
                WHERE sha1={sha1}""",
            sha1=sha1,
        ) as result:
            try:
                return await result.scalar()
            except result.ZeroRowsInResult:
                raise api.commit.InvalidSHA1(value=sha1)

    async def sha1_from_commit_id() -> SHA1:
        assert commit_id
        async with api.critic.Query[SHA1](
            critic,
            """SELECT sha1
                 FROM commits
                WHERE id={commit_id}""",
            commit_id=commit_id,
        ) as result:
            try:
                return await result.scalar()
            except result.ZeroRowsInResult:
                raise api.commit.InvalidId(invalid_id=commit_id)

    if ref is not None:
        sha1 = await repository.resolveRef(ref, expect="commit")

    if commit_id is not None:
        try:
            return Commit.get_cached(critic, (repository_id, commit_id))
        except KeyError:
            pass

        if sha1 is None:
            sha1 = await sha1_from_commit_id()
    else:
        assert sha1

        try:
            return Commit.get_cached(critic, (repository_id, sha1))
        except KeyError:
            pass

        commit_id = await commit_id_from_sha1()

    return Commit.create(
        critic,
        (
            repository,
            commit_id,
            await repository.low_level.fetchone(sha1, wanted_object_type="commit"),
        ),
    )


async def fetchMany(
    repository: api.repository.Repository,
    commit_ids: Optional[Iterable[int]],
    sha1s: Optional[Iterable[SHA1]],
    low_levels: Optional[Iterable[gitaccess.GitCommit]],
) -> Sequence[WrapperType]:
    critic = repository.critic

    critic._impl.initializeObjects(Commit)
    all_cached_commits = Commit.get_all_cached(critic)

    repository_id = int(repository)

    if commit_ids is not None:
        commits = {
            commit_id: all_cached_commits[(repository_id, commit_id)]
            for commit_id in commit_ids
            if (repository_id, commit_id) in all_cached_commits
        }

        missing_commit_ids = set(
            commit_id for commit_id in commit_ids if commit_id not in commits
        )

        if missing_commit_ids:
            async with api.critic.Query[Tuple[int, SHA1]](
                critic,
                """SELECT id, sha1
                     FROM commits
                    WHERE {id=commit_ids:array}""",
                commit_ids=list(missing_commit_ids),
            ) as result:
                rows = await result.all()

            if len(rows) != len(missing_commit_ids):
                found_ids = set(commit_id for commit_id, _ in rows)
                for commit_id in found_ids - missing_commit_ids:
                    raise api.commit.InvalidId(invalid_id=commit_id)

            sha1s = [sha1 for _, sha1 in rows]
            commit_id_from_sha1 = {sha1: commit_id for commit_id, sha1 in rows}

            async for _, low_level in repository.low_level.fetch(
                *sha1s, object_factory=gitaccess.GitCommit
            ):
                if isinstance(low_level, gitaccess.GitFetchError):
                    raise low_level
                commit_id = commit_id_from_sha1[low_level.sha1]
                commits[commit_id] = Commit.create(
                    critic, (repository, commit_id, low_level)
                )

        return [commits[commit_id] for commit_id in commit_ids]

    if low_levels is not None:
        sha1s = [low_level.sha1 for low_level in low_levels]
        low_level_from_sha1 = {low_level.sha1: low_level for low_level in low_levels}
    else:
        assert sha1s
        sha1s = list(sha1s)

    async with api.critic.Query[Tuple[int, SHA1]](
        critic,
        """SELECT id, sha1
             FROM commits
            WHERE {sha1=sha1s:array}""",
        sha1s=list(sha1s),
    ) as result:
        rows = await result.all()

    if len(rows) != len(set(sha1s)):
        found_sha1s = set(sha1 for _, sha1 in rows)
        for sha1 in sha1s:
            if sha1 not in found_sha1s:
                raise api.commit.InvalidSHA1(value=sha1)

    commit_id_from_sha1 = {}
    missing_sha1s = set()

    for commit_id, sha1 in rows:
        commit_id_from_sha1[sha1] = commit_id
        if (repository_id, commit_id) not in all_cached_commits:
            missing_sha1s.add(sha1)

    if missing_sha1s:
        if low_levels:
            for sha1 in missing_sha1s:
                commit_id = commit_id_from_sha1[sha1]
                Commit.create(
                    critic, (repository, commit_id, low_level_from_sha1[sha1])
                )
        else:
            async for _, low_level in repository.low_level.fetch(
                *missing_sha1s, object_factory=gitaccess.GitCommit
            ):
                if isinstance(low_level, gitaccess.GitFetchError):
                    raise low_level
                commit_id = commit_id_from_sha1[low_level.sha1]
                Commit.create(critic, (repository, commit_id, low_level))

    return [
        all_cached_commits[(repository_id, commit_id_from_sha1[sha1])] for sha1 in sha1s
    ]


async def fetchRange(
    from_commit: Optional[api.commit.Commit],
    to_commit: api.commit.Commit,
    order: api.commit.Order,
    offset: Optional[int],
    count: Optional[int],
) -> api.commitset.CommitSet:
    critic = to_commit.critic
    repository = to_commit.repository

    # Optimization: it's not uncommon that this function ends up being used for
    #               a parent-child pair, in which case this is much faster.
    if from_commit and to_commit.low_level.parents == [from_commit.sha1]:
        return await api.commitset.create(critic, [to_commit])

    include = [str(to_commit)]
    exclude = [str(from_commit)] if from_commit else []

    git_commits = {}
    async for _, git_object in repository.low_level.fetch(
        include=include,
        exclude=exclude,
        order=order,
        skip=offset,
        limit=count,
        wanted_object_type="commit",
    ):
        if isinstance(git_object, gitaccess.GitFetchError):
            raise git_object
        git_commit = git_object.asCommit()
        git_commits[git_commit.sha1] = git_commit
    if not git_commits:
        return api.commitset.empty(critic)

    async with api.critic.Query[Tuple[int, SHA1]](
        critic,
        """SELECT id, sha1
             FROM commits
            WHERE {sha1=sha1s:array}""",
        sha1s=list(git_commits.keys()),
    ) as result:
        commits = [
            Commit.create(critic, (repository, commit_id, git_commits[sha1]))
            async for commit_id, sha1 in result
        ]

    assert len(commits) == len(git_commits)

    return await api.commitset.create(critic, commits)


async def prefetch(
    repository: api.repository.Repository, commit_ids: Iterable[int]
) -> None:
    critic = repository.critic
    repository_id = repository.id

    async with api.critic.Query[int](
        critic,
        """SELECT DISTINCT parent
             FROM edges
            WHERE {child=commit_ids:array}""",
        commit_ids=list(commit_ids),
    ) as result:
        commit_ids = set(commit_ids) | set(await result.scalars())

    try:
        all_cached = Commit.get_all_cached(critic)
        commit_ids = [
            commit_id
            for commit_id in commit_ids
            if (repository_id, commit_id) not in all_cached
        ]
    except KeyError:
        pass

    await fetchMany(repository, commit_ids, None, None)
