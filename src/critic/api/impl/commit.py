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
from typing import Collection, Iterable, Sequence, Tuple, Optional, Union, cast


logger = logging.getLogger(__name__)

from critic import api
from critic.api import commit as public
from critic.api.repository import Decode
from critic import diff
from critic import gitaccess
from critic.gitaccess import SHA1
from .apiobject import APIObjectImplWithId

RE_FOLLOWUP = re.compile("(fixup|squash)!.*(?:\n[ \t]*)+(.*)")


@dataclass(frozen=True)
class UserAndTimestamp:
    __name: str
    __email: str
    __timestamp: datetime.datetime

    @property
    def name(self) -> str:
        return self.__name

    @property
    def email(self) -> str:
        return self.__email

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp


@dataclass(frozen=True)
class FileInformation:
    __file: api.file.File
    __mode: int
    __sha1: SHA1
    __size: int

    @property
    def file(self) -> api.file.File:
        return self.__file

    @property
    def mode(self) -> int:
        return self.__mode

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    @property
    def size(self) -> int:
        return self.__size


@dataclass
class CommitMetadata:
    author: UserAndTimestamp
    committer: UserAndTimestamp
    message: str
    low_level: gitaccess.GitCommit

    @staticmethod
    async def make(decode: Decode, low_level: gitaccess.GitCommit) -> CommitMetadata:
        return CommitMetadata(
            UserAndTimestamp(
                decode.commitMetadata(low_level.author.name),
                decode.commitMetadata(low_level.author.email),
                low_level.author.time,
            ),
            UserAndTimestamp(
                decode.commitMetadata(low_level.committer.name),
                decode.commitMetadata(low_level.committer.email),
                low_level.committer.time,
            ),
            decode.commitMetadata(low_level.message),
            low_level,
        )


PublicType = public.Commit
ArgumentsType = Tuple[api.repository.Repository, int, CommitMetadata]
CacheKeyType = Tuple[int, Union[int, SHA1]]


class Commit(PublicType, APIObjectImplWithId, module=public):
    __description: Optional[CommitDescription]

    def __init__(
        self,
        repository: api.repository.Repository,
        commit_id: int,
        metadata: CommitMetadata,
    ):
        super().__init__(repository.critic, (repository, commit_id, metadata))

    def update(self, args: ArgumentsType) -> int:
        (self.__repository, self.__id, metadata) = args
        self.__author = metadata.author
        self.__committer = metadata.committer
        self.__message = metadata.message
        self.__low_level = metadata.low_level
        self.__sha1 = self.__low_level.sha1
        self.__tree = self.__low_level.tree
        return self.id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def repository(self) -> api.repository.Repository:
        return self.__repository

    @property
    def sha1(self) -> SHA1:
        return self.__sha1

    @property
    def tree(self) -> SHA1:
        return self.__tree

    @property
    def summary(self) -> str:
        match = RE_FOLLOWUP.match(self.__message)
        if match:
            followup_type, summary = match.groups()
            return "[%s] %s" % (followup_type, summary)
        return self.__message.split("\n", 1)[0]

    @property
    def message(self) -> str:
        return self.__message

    @property
    def is_merge(self) -> bool:
        return len(self.__low_level.parents) > 1

    @property
    async def parents(self) -> Sequence[PublicType]:
        if not self.__low_level.parents:
            return ()
        return await fetchMany(self.repository, None, self.__low_level.parents, None)

    @property
    def low_level(self) -> gitaccess.GitCommit:
        return self.__low_level

    @property
    async def description(self) -> public.CommitDescription:
        if self.__description is None:
            self.__description = CommitDescription(self)
            await self.__description.calculateBranch()
        return self.__description

    @property
    def author(self) -> PublicType.UserAndTimestamp:
        return self.__author

    @property
    def committer(self) -> PublicType.UserAndTimestamp:
        return self.__committer

    def isParentOf(self, child: PublicType) -> bool:
        return self.__low_level.sha1 in child.low_level.parents

    async def isAncestorOf(self, commit: PublicType) -> bool:
        return await self.repository.low_level.mergebase(
            self.sha1, commit.sha1, is_ancestor=True
        )

    async def getFileInformation(
        self, file: api.file.File
    ) -> Optional[PublicType.FileInformation]:
        entries = await self.repository.low_level.lstree(
            self.sha1, file.path, long_format=True
        )
        if not entries:
            return None
        entry = entries[0]
        if len(entries) > 1 or entry.object_type != "blob" or not entry.isreg():
            raise public.NotAFile(file.path)
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
        decode = await self.repository.getDecode(self)
        return diff.parse.splitlines(decode.fileContent(file.path)(contents))

    def getCacheKeys(self) -> Collection[object]:
        return ((self.repository, self.id), (self.repository, self.sha1))

    @classmethod
    async def doRefreshAll(
        cls, critic: api.critic.Critic, commits: Collection[object], /
    ) -> None:
        pass


class CommitDescription:
    __branch: Optional[api.branch.Branch]

    def __init__(self, commit: public.Commit) -> None:
        self.__commit = commit
        self.__branch = None

    @property
    def commit(self) -> public.Commit:
        return self.__commit

    @property
    def branch(self) -> Optional[api.branch.Branch]:
        return self.__branch

    async def calculateBranch(self) -> None:
        critic = self.__commit.critic
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
                self.__branch = await api.branch.fetch(critic, await result.scalar())
            except result.ZeroRowsInResult:
                pass

    # async def getTag(self, critic: api.critic.Critic):
    #     # FIXME: Support tags.
    #     return None


async def commit_id_from_sha1(critic: api.critic.Critic, sha1: SHA1) -> int:
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
            raise public.InvalidSHA1(value=sha1)


async def sha1_from_commit_id(critic: api.critic.Critic, commit_id: int) -> SHA1:
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
            raise public.InvalidId(value=commit_id)


async def makeCommit(
    repository: api.repository.Repository, commit_id: int, sha1: SHA1
) -> Commit:
    return Commit(
        repository,
        commit_id,
        await CommitMetadata.make(
            await repository.getDecode(),
            (
                await repository.low_level.fetchone(sha1, wanted_object_type="commit")
            ).asCommit(),
        ),
    )


async def fetch_by_id(args: Tuple[api.repository.Repository, int]) -> Commit:
    repository, commit_id = args
    return await makeCommit(
        repository, commit_id, await sha1_from_commit_id(repository.critic, commit_id)
    )


async def fetch_by_sha1(args: Tuple[api.repository.Repository, SHA1]) -> Commit:
    repository, sha1 = args
    return await makeCommit(
        repository, await commit_id_from_sha1(repository.critic, sha1), sha1
    )


async def fetch_by_rows(
    repository: api.repository.Repository, rows: Sequence[Tuple[SHA1, int]]
) -> Collection[Commit]:
    commit_id_by_sha1 = dict(rows)
    commits = set()
    decode = await repository.getDecode()
    async for sha1, gitobject in repository.low_level.fetch(
        *commit_id_by_sha1.keys(), wanted_object_type="commit"
    ):
        if isinstance(gitobject, gitaccess.GitFetchError):
            raise gitobject
        commits.add(
            Commit(
                repository,
                commit_id_by_sha1[sha1],
                await CommitMetadata.make(decode, gitobject.asCommit()),
            )
        )
    return commits


async def lookup_ids(
    critic: api.critic.Critic, sha1s: Sequence[SHA1]
) -> Sequence[Tuple[SHA1, int]]:
    async with api.critic.Query[Tuple[SHA1, int]](
        critic,
        """
        SELECT sha1, id
          FROM commits
         WHERE sha1=ANY({sha1s})
        """,
        sha1s=sha1s,
    ) as result:
        return await result.all()


async def fetch_by_ids(
    args: Sequence[Tuple[api.repository.Repository, int]]
) -> Collection[Commit]:
    assert len(args) != 0
    repository = args[0][0]
    commit_ids = [commit_id for _, commit_id in args]
    async with api.critic.Query[Tuple[SHA1, int]](
        repository.critic,
        """
        SELECT sha1, id
          FROM commits
         WHERE id=ANY({commit_ids})
        """,
        commit_ids=commit_ids,
    ) as result:
        rows = await result.all()
    return await fetch_by_rows(repository, rows)


async def fetch_by_sha1s(
    args: Sequence[Tuple[api.repository.Repository, SHA1]]
) -> Collection[Commit]:
    assert len(args) != 0
    assert len(set(repository for repository, _ in args)) == 1
    repository = args[0][0]
    sha1s = [sha1 for _, sha1 in args]
    return await fetch_by_rows(repository, await lookup_ids(repository.critic, sha1s))


@public.fetchImpl
async def fetch(
    repository: api.repository.Repository,
    commit_id: Optional[int],
    sha1: Optional[SHA1],
    ref: Optional[str],
) -> PublicType:
    if commit_id is not None:
        return await Commit.ensureOne((repository, commit_id), fetch_by_id)
    if ref is not None:
        sha1 = await repository.resolveRef(ref, expect="commit")
    assert sha1
    return await Commit.ensureOne((repository, sha1), fetch_by_sha1)


@public.fetchManyImpl
async def fetchMany(
    repository: api.repository.Repository,
    commit_ids: Optional[Iterable[int]],
    sha1s: Optional[Iterable[SHA1]],
    low_levels: Optional[Iterable[gitaccess.GitCommit]],
) -> Sequence[PublicType]:
    critic = repository.critic

    if commit_ids is not None:
        return await Commit.ensure(
            [(repository, commit_id) for commit_id in commit_ids], fetch_by_ids
        )

    if sha1s is not None:
        return await Commit.ensure(
            [(repository, sha1) for sha1 in sha1s], fetch_by_sha1s
        )

    assert low_levels is not None
    low_levels = [*low_levels]
    sha1s = [low_level.sha1 for low_level in low_levels]
    low_level_by_sha1 = {low_level.sha1: low_level for low_level in low_levels}
    commit_id_by_sha1 = dict(await lookup_ids(critic, sha1s))
    decode = await repository.getDecode()

    return Commit.store(
        [
            Commit(
                repository,
                commit_id_by_sha1[sha1],
                await CommitMetadata.make(decode, low_level_by_sha1[sha1]),
            )
            for sha1 in sha1s
        ]
    )


@public.fetchRangeImpl
async def fetchRange(
    from_commit: Optional[public.Commit],
    to_commit: public.Commit,
    order: public.Order,
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

    low_levels = []
    async for _, gitobject in repository.low_level.fetch(
        include=include,
        exclude=exclude,
        order=order,
        skip=offset,
        limit=count,
        wanted_object_type="commit",
    ):
        if isinstance(gitobject, gitaccess.GitFetchError):
            raise gitobject
        low_levels.append(gitobject.asCommit())
    if not low_levels:
        return api.commitset.empty(critic)

    return await api.commitset.create(
        critic, await fetchMany(repository, None, None, low_levels)
    )


@public.prefetchImpl
async def prefetch(
    repository: api.repository.Repository, commit_ids: Iterable[int]
) -> None:
    critic = repository.critic

    async with api.critic.Query[int](
        critic,
        """SELECT DISTINCT parent
             FROM edges
            WHERE child=ANY({commit_ids})""",
        commit_ids=list(commit_ids),
    ) as result:
        commit_ids = set(commit_ids) | set(await result.scalars())

    cached = Commit.allCached()
    missing_ids = set(
        commit_id for commit_id in commit_ids if (repository, commit_id) not in cached
    )

    if missing_ids:
        await fetchMany(repository, missing_ids, None, None)
