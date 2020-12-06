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
import contextlib

import logging
import os
from dataclasses import dataclass
from typing import (
    Iterator,
    Optional,
    Iterable,
    Tuple,
    List,
    Sequence,
    Set,
    TypeVar,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import repository as public
from critic import auth
from critic import gitaccess
from critic.background import gitaccessor
from critic.background.utils import is_services
from critic.gitaccess import SHA1, ObjectType
from . import apiobject
from .critic import Critic

STATISTICS = "Repository.statistics"


@dataclass(frozen=True)
class Statistics:
    __commits: int
    __branches: int
    __reviews: int

    @property
    def commits(self) -> int:
        return self.__commits

    @property
    def branches(self) -> int:
        return self.__branches

    @property
    def reviews(self) -> int:
        return self.__reviews


WrapperType = api.repository.Repository
ArgumentsType = Tuple[int, str, str, bool]

T = TypeVar("T")


@dataclass
class Head:
    __wrapper: api.repository.Repository
    __impl: Repository

    @property
    async def value(self) -> Optional[str]:
        return await self.__impl.getHeadValue(self.__wrapper)

    @property
    async def commit(self) -> Optional[api.commit.Commit]:
        return await self.__impl.getHeadCommit(self.__wrapper)

    @property
    async def branch(self) -> Optional[api.branch.Branch]:
        return await self.__impl.getHeadBranch(self.__wrapper)


class Repository(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    table_name = "repositories"
    column_names = ["id", "name", "path", "ready"]

    __low_level: Optional[gitaccess.GitRepository]
    __statistics: Optional[WrapperType.Statistics]

    def __init__(self, args: ArgumentsType) -> None:
        (self.id, self.name, self.path, self.is_ready) = args
        self.__low_level = None
        self.__statistics = None

    @staticmethod
    async def checkAccess(wrapper: WrapperType) -> None:
        await auth.AccessControl.accessRepository(wrapper, "read")

    @staticmethod
    async def filterInaccessible(
        repositories: Iterable[WrapperType],
    ) -> List[WrapperType]:
        result = []
        for repository in repositories:
            try:
                await Repository.checkAccess(repository)
            except auth.AccessDenied:
                pass
            else:
                result.append(repository)
        return result

    async def isReady(self, critic: api.critic.Critic) -> bool:
        if not self.is_ready:
            async with critic.query(
                """SELECT ready
                     FROM repositories
                    WHERE id={repository_id}""",
                repository_id=self.id,
            ) as result:
                self.is_ready = await result.scalar()
        return self.is_ready

    async def getDocumentationPath(self, wrapper: WrapperType) -> Optional[str]:
        commit = await self.getHeadCommit(wrapper)
        if commit is None:
            return None
        candidate_paths = api.critic.settings().repositories.default_documentation_paths
        for candidate_path in candidate_paths:
            file = await api.file.fetch(
                wrapper.critic, path=candidate_path, create_if_missing=True
            )
            try:
                await commit.getFileInformation(file)
                return candidate_path
            except api.commit.NotAFile:
                pass
        return None

    def getLowLevel(self, critic: api.critic.Critic) -> gitaccess.GitRepository:
        if not self.__low_level:
            assert self.__low_level is None
            if is_services():
                self.__low_level = gitaccess.GitRepository.direct(self.path)
            else:
                self.__low_level = gitaccessor.GitRepositoryProxy.make(self.path)
            critic.addCloseTask(self.__low_level.close)
        return self.__low_level

    @contextlib.contextmanager
    def withSystemUserDetails(
        self, critic: api.critic.Critic, author: bool, committer:bool
    ) -> Iterator[gitaccess.GitRepository]:
        settings = api.critic.settings()
        low_level = self.getLowLevel(critic)
        name = settings.repositories.system_user_details.name
        email = settings.repositories.system_user_details.email
        if email is None:
            email = f"critic@{settings.system.hostname}"
        if author:
            low_level.set_author_details(name, email)
        if committer:
            low_level.set_committer_details(name, email)
        try:
            yield low_level
        finally:
            low_level.clear_user_details()

    async def getSetting(self, wrapper: WrapperType, name: str, default: T) -> T:
        value, is_set = await api.usersetting.get(
            wrapper.critic, "repository", f"{name}.{wrapper.name}", default=default
        )
        if not is_set:
            value, is_set = await api.usersetting.get(
                wrapper.critic, "repository", f"{name}", default=default
            )
        if not is_set:
            value, is_set = await api.repositorysetting.get(
                wrapper.critic, wrapper, "system", name, default=default
            )
        return value

    async def getURLs(self, wrapper: WrapperType) -> Sequence[str]:
        critic = wrapper.critic
        hostname = api.critic.settings().system.hostname
        url_types = set(
            await self.getSetting(wrapper, "urlTypes", ["git", "host", "http"])
        )
        urls = []

        if "git" in url_types:
            urls.append(f"git://{hostname}/{self.path}")
        if "ssh" in url_types or "host" in url_types:
            if "ssh" in url_types:
                urls.append(f"ssh://{hostname}/{self.path}")
            if "host" in url_types:
                urls.append(f"{hostname}:{self.path}")
        if "http" in url_types:
            for url_prefix in await critic.effective_user.url_prefixes:
                urls.append(f"{url_prefix}/{self.path.lstrip('/')}")

        return urls

    def getHead(self, wrapper: WrapperType) -> public.Repository.Head:
        return Head(wrapper, self)

    async def getHeadValue(self, wrapper: WrapperType) -> Optional[str]:
        try:
            return await wrapper.low_level.symbolicref("HEAD")
        except gitaccess.GitError:
            return None

    async def getHeadCommit(self, wrapper: WrapperType) -> Optional[api.commit.Commit]:
        value = await self.getHeadValue(wrapper)
        if value is None:
            return None
        try:
            return await api.commit.fetch(wrapper, ref=value)
        except api.repository.InvalidRef:
            return None

    async def getHeadBranch(self, wrapper: WrapperType) -> Optional[api.branch.Branch]:
        value = await self.getHeadValue(wrapper)
        if value is None:
            return None
        if value.startswith("refs/heads/"):
            try:
                return await api.branch.fetch(
                    wrapper.critic,
                    repository=wrapper,
                    name=value[len("refs/heads/") :],
                )
            except api.branch.InvalidName:
                # It is possible for HEAD to reference a ref that does not
                # exist.
                return None
        else:
            return None

    async def resolveRef(
        self, wrapper: WrapperType, ref: str, expect: ObjectType, short: bool
    ) -> str:
        try:
            if short:
                return await wrapper.low_level.revparse(
                    ref, object_type=expect, short=True
                )
            else:
                return await wrapper.low_level.revparse(ref, object_type=expect)
        except gitaccess.GitReferenceError:
            raise api.repository.InvalidRef(ref)

    async def listRefs(
        self, wrapper: WrapperType, pattern: Optional[str]
    ) -> Sequence[str]:
        try:
            return await wrapper.low_level.foreachref(pattern=pattern)
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )

    async def listCommits(
        self,
        wrapper: WrapperType,
        include: Iterable[str],
        exclude: Iterable[str],
        paths: Optional[Iterable[str]],
        min_parents: Optional[int],
        max_parents: Optional[int],
    ) -> Sequence[api.commit.Commit]:
        try:
            sha1s = await wrapper.low_level.revlist(
                include,
                exclude,
                paths=paths,
                min_parents=min_parents,
                max_parents=max_parents,
            )
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )
        return await api.commit.fetchMany(wrapper, sha1s=sha1s)

    async def mergeBase(
        self, wrapper: WrapperType, *commits: api.commit.Commit
    ) -> api.commit.Commit:
        try:
            sha1 = await wrapper.low_level.mergebase(
                *(commit.sha1 for commit in commits)
            )
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )
        return await api.commit.fetch(wrapper, sha1=sha1)

    async def protectCommit(self, commit: api.commit.Commit) -> None:
        await self.getLowLevel(commit.critic).updateref(
            "refs/keepalive/" + commit.sha1, new_value=commit.sha1
        )

    async def getFileContents(
        self,
        repository: WrapperType,
        commit: Optional[api.commit.Commit],
        file: Optional[api.file.File],
        sha1: Optional[SHA1],
    ) -> Optional[bytes]:
        if commit is not None:
            assert file is not None
            information = await commit.getFileInformation(file)
            if information is None:
                return None
            sha1 = information.sha1
        assert sha1 is not None
        return cast(
            gitaccess.GitBlob,
            await self.getLowLevel(repository.critic).fetchone(
                sha1, wanted_object_type="blob"
            ),
        ).data

    @staticmethod
    async def __loadStatistics(critic: api.critic.Critic) -> None:
        cached_objects = dict(Repository.allCached(critic))

        need_fetch = []
        for repository in cached_objects.values():
            if Repository.fromWrapper(repository).__statistics is None:
                need_fetch.append(repository.id)

        commits = {}
        branches = {}
        reviews = {}

        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT repository, SUM(size)
                 FROM branches
                WHERE type='normal'
                  AND NOT merged
                  AND {repository=need_fetch:array}
             GROUP BY repository""",
            need_fetch=need_fetch,
        ) as commits_result:
            async for repository_id, sum_size in commits_result:
                commits[repository_id] = sum_size

        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT repository, COUNT(*)
                 FROM branches
                WHERE type='normal'
                  AND {repository=need_fetch:array}
             GROUP BY repository""",
            need_fetch=need_fetch,
        ) as branches_result:
            async for repository_id, count_branches in branches_result:
                branches[repository_id] = count_branches

        async with api.critic.Query[Tuple[int, int]](
            critic,
            """SELECT repository, COUNT(*)
                 FROM reviews
                WHERE state IN ('open', 'closed')
                  AND {repository=need_fetch:array}
             GROUP BY repository""",
            need_fetch=need_fetch,
        ) as reviews_result:
            async for repository_id, count_reviews in reviews_result:
                reviews[repository_id] = count_reviews

        for repository_id in need_fetch:
            Repository.fromWrapper(
                cached_objects[repository_id]
            ).__statistics = Statistics(
                commits.get(repository_id, 0),
                branches.get(repository_id, 0),
                reviews.get(repository_id, 0),
            )

    async def getStatistics(self, critic: api.critic.Critic) -> WrapperType.Statistics:
        async with Critic.fromWrapper(critic).criticalSection(STATISTICS):
            if self.__statistics is None:
                await self.__loadStatistics(critic)
                assert self.__statistics is not None
        return self.__statistics


@public.fetchImpl
@Repository.cached
async def fetch(
    critic: api.critic.Critic,
    repository_id: Optional[int],
    name: Optional[str],
    path: Optional[str],
) -> WrapperType:
    if repository_id is not None:
        condition = "id={repository_id}"
    elif name is not None:
        condition = "name={name}"
    else:
        condition = "path={path}"
    async with Repository.query(
        critic, [condition], repository_id=repository_id, name=name, path=path
    ) as result:
        try:
            repository = await Repository.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if repository_id is not None:
                raise api.repository.InvalidId(invalid_id=repository_id)
            if name is not None:
                raise api.repository.InvalidName(value=name)
            assert path is not None
            raise api.repository.InvalidRepositoryPath(path)
    await Repository.checkAccess(repository)
    return repository


@public.fetchAllImpl
async def fetchAll(critic: api.critic.Critic) -> Sequence[WrapperType]:
    async with Repository.query(critic) as result:
        repositories = await Repository.make(
            critic, result, ignored_errors=(auth.AccessDenied,)
        )
    return await Repository.filterInaccessible(repositories)


@public.fetchHighlightedImpl
async def fetchHighlighted(
    critic: api.critic.Critic, user: api.user.User
) -> Sequence[WrapperType]:
    highlighted_ids: Set[int] = set()

    async with api.critic.Query[int](
        critic,
        """SELECT DISTINCT repository
             FROM repositoryfilters
            WHERE uid={user_id}""",
        user_id=user.id,
    ) as ids_result:
        highlighted_ids.update(await ids_result.scalars())

    async with api.critic.Query[int](
        critic,
        """SELECT DISTINCT repository
             FROM branches
             JOIN reviews ON (reviews.branch=branches.id)
             JOIN reviewusers ON (reviewusers.review=reviews.id)
            WHERE reviewusers.uid={user_id}
              AND reviewusers.owner""",
        user_id=user.id,
    ) as ids_result:
        highlighted_ids.update(await ids_result.scalars())

    async with Repository.query(
        critic,
        ["id={repository_ids}"],
        repository_ids=list(highlighted_ids),
    ) as result:
        repositories = await Repository.make(
            critic, result, ignored_errors=(auth.AccessDenied,)
        )

    return await Repository.filterInaccessible(repositories)


@public.validateNameImpl
def validateName(name: str) -> str:
    if "/" in name:
        raise api.repository.Error(
            "repository name can not contain a forward slash ('/')"
        )

    if name.strip() != name:
        raise api.repository.Error(
            "repository name can not have leading or trailing white-space"
        )

    if not name:
        raise api.repository.Error("repository name can not be empty")

    if len(name) > 64:
        raise api.repository.Error(
            "repository name is too long (limit is 64 characters)"
        )

    return name


@public.validatePathImpl
def validatePath(path: str) -> str:
    if path.startswith(os.sep):
        raise api.repository.Error("repository path must be relative")

    if not path.endswith(".git"):
        raise api.repository.Error("repository path must end with '.git'")

    normalized_path = os.path.normpath(path)
    if normalized_path != path:
        raise api.repository.Error(
            f"normalized repository path is different: {normalized_path!r} != {path!r}"
        )

    return path
