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

import asyncio
import codecs
import logging
import os
import re
from dataclasses import dataclass
from typing import (
    Callable,
    ClassVar,
    Collection,
    Dict,
    Iterator,
    Literal,
    Optional,
    Iterable,
    Tuple,
    List,
    Sequence,
    Set,
    TypeVar,
    Union,
    cast,
    overload,
)

from .queryhelper import QueryHelper, QueryResult

logger = logging.getLogger(__name__)

from critic import api, dbaccess
from critic.api import repository as public
from critic import auth
from critic import gitaccess
from critic.background import gitaccessor
from critic.background.utils import is_services
from critic.gitaccess import SHA1, ObjectType
from critic.reviewing.filters import validatePattern, compilePattern, PatternError
from .apiobject import APIObjectImplWithId

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


PublicType = api.repository.Repository
ArgumentsType = Tuple[int, str, str, bool]

T = TypeVar("T")


@dataclass
class Head:
    __repository: Repository

    @property
    async def value(self) -> Optional[str]:
        return await self.__repository.getHeadValue()

    @property
    async def commit(self) -> Optional[api.commit.Commit]:
        return await self.__repository.getHeadCommit()

    @property
    async def branch(self) -> Optional[api.branch.Branch]:
        return await self.__repository.getHeadBranch()


class Encodings:
    def __init__(self, encodings: Sequence[str]):
        self.__candidates = encodings[:-1]
        self.__fallback = encodings[-1]

    @property
    def value(self) -> Sequence[str]:
        return [*self.__candidates, self.__fallback]

    def __call__(self, value: bytes) -> str:
        for encoding in self.__candidates:
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                pass
        return value.decode(self.__fallback, errors="replace")


class FileEncodings:
    __entries: List[Tuple[re.Pattern[str], Encodings]]

    def __init__(self, default: Encodings) -> None:
        self.__entries = []
        self.__default = default

    def read(
        self, repository_path: str, commit_sha1: SHA1, source: str
    ) -> FileEncodings:
        base_prefix = f"[{repository_path}/.critic/encodings @ {commit_sha1[:8]}]"
        for index, line in enumerate(map(str.strip, source.splitlines())):
            if line.startswith("#"):
                continue
            prefix = f"{base_prefix}:{index + 1}"
            try:
                pattern, *unchecked_encodings = line.split()
            except ValueError:
                logger.warn("%s: invalid line: %r", prefix, line)
                continue
            try:
                validatePattern(pattern)
            except PatternError as error:
                logger.warn("%s: invalid pattern: %r (%s)", prefix, pattern, error)
            encodings: List[str] = []
            for encoding in unchecked_encodings:
                try:
                    codecs.lookup(encoding)
                except LookupError:
                    logger.warn("%s: invalid encoding: %r", prefix, encoding)
                else:
                    encodings.append(encoding)
            if encodings:
                self.__entries.append((compilePattern(pattern), Encodings(encodings)))
            else:
                logger.warn("%s: invalid line: %r (no valid encodings)", prefix, line)
        return self

    def __call__(self, path: str) -> Encodings:
        for pattern, encodings in self.__entries:
            if pattern.match(path):
                return encodings
        return self.__default


@dataclass
class Decode:
    __commit_metadata: Encodings
    __file_content: FileEncodings
    __path: Encodings

    def commitMetadata(self, value: bytes) -> str:
        return self.__commit_metadata(value)

    def getCommitMetadataEncodings(self) -> Sequence[str]:
        return self.__commit_metadata.value

    def fileContent(self, path: str) -> Encodings:
        return self.__file_content(path)

    def getFileContentEncodings(self, path: str) -> Sequence[str]:
        return self.__file_content(path).value

    def path(self, value: bytes) -> str:
        return self.__path(value)

    def getPathEncodings(self) -> Sequence[str]:
        return self.__path.value


class Repository(PublicType, APIObjectImplWithId, module=public):
    __default_encodings: ClassVar[Dict[str, Encodings]] = {}
    __file_encodings: ClassVar[Dict[SHA1, FileEncodings]] = {}
    __decode: ClassVar[Dict[Optional[SHA1], Decode]] = {}

    __low_level: Optional[gitaccess.GitRepository] = None
    __statistics: Optional[PublicType.Statistics]

    def update(self, args: ArgumentsType) -> int:
        if self.__low_level:
            asyncio.create_task(self.__low_level.close())
        (self.__id, self.__name, self.__path, self.__is_ready) = args
        self.__low_level = None
        self.__statistics = None
        return self.__id

    async def checkAccess(self) -> None:
        await auth.AccessControl.accessRepository(self, "read")

    @staticmethod
    async def filterInaccessible(
        repositories: Iterable[Repository],
    ) -> List[Repository]:
        result = []
        for repository in repositories:
            try:
                await repository.checkAccess()
            except auth.AccessDenied:
                pass
            else:
                result.append(repository)
        return result

    @property
    def id(self) -> int:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def path(self) -> str:
        return self.__path

    @property
    async def is_ready(self) -> bool:
        if not self.__is_ready:
            async with api.critic.Query[bool](
                self.critic,
                """SELECT ready
                     FROM repositories
                    WHERE id={repository_id}""",
                repository_id=self.id,
            ) as result:
                self.__is_ready = await result.scalar()
        return self.__is_ready

    @property
    async def documentation_path(self) -> Optional[str]:
        commit = await self.getHeadCommit()
        if commit is None:
            return None
        candidate_paths = api.critic.settings().repositories.default_documentation_paths
        for candidate_path in candidate_paths:
            file = await api.file.fetch(
                self.critic, path=candidate_path, create_if_missing=True
            )
            try:
                await commit.getFileInformation(file)
                return candidate_path
            except api.commit.NotAFile:
                pass
        return None

    @property
    def low_level(self) -> gitaccess.GitRepository:
        if not self.__low_level:
            assert self.__low_level is None
            if is_services():
                self.__low_level = gitaccess.GitRepository.direct(self.path)
            else:
                self.__low_level = gitaccessor.GitRepositoryProxy.make(self.path)
            self.critic.addCloseTask(self.__low_level.close)
        return self.__low_level

    @contextlib.contextmanager
    def withSystemUserDetails(
        self, *, author: bool = True, committer: bool = True
    ) -> Iterator[gitaccess.GitRepository]:
        settings = api.critic.settings()
        low_level = self.low_level
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

    # def withSystemUserDetails(
    #     self, *, author: bool = True, committer: bool = True
    # ) -> ContextManager[gitaccess.GitRepository]:

    async def getSetting(self, name: str, default: T) -> T:
        value, is_set = await api.usersetting.get(
            self.critic, "repository", f"{name}.{self.name}", default=default
        )
        if not is_set:
            value, is_set = await api.usersetting.get(
                self.critic, "repository", f"{name}", default=default
            )
        if not is_set:
            value, is_set = await api.repositorysetting.get(
                self.critic, self, "system", name, default=default
            )
        return value

    @property
    async def urls(self) -> Sequence[str]:
        hostname = api.critic.settings().system.hostname
        http_prefix = api.critic.settings().system.http_prefix
        url_types = set(await self.getSetting("urlTypes", ["git", "host", "http"]))
        urls = []

        if "git" in url_types:
            urls.append(f"git://{hostname}/{self.path}")
        if "ssh" in url_types or "host" in url_types:
            if "ssh" in url_types:
                urls.append(f"ssh://{hostname}/{self.path}")
            if "host" in url_types:
                urls.append(f"{hostname}:{self.path}")
        if "http" in url_types:
            urls.append(f"{http_prefix}/{self.path.lstrip('/')}")

        return urls

    @property
    def head(self) -> public.Repository.Head:
        return Head(self)

    async def getHeadValue(self) -> Optional[str]:
        try:
            return await self.low_level.symbolicref("HEAD")
        except gitaccess.GitError:
            return None

    async def getHeadCommit(self) -> Optional[api.commit.Commit]:
        value = await self.getHeadValue()
        if value is None:
            return None
        try:
            return await api.commit.fetch(self, ref=value)
        except api.repository.InvalidRef:
            return None

    async def getHeadBranch(self) -> Optional[api.branch.Branch]:
        value = await self.getHeadValue()
        if value is None:
            return None
        if value.startswith("refs/heads/"):
            try:
                return await api.branch.fetch(
                    self.critic,
                    repository=self,
                    name=value[len("refs/heads/") :],
                )
            except api.branch.InvalidName:
                # It is possible for HEAD to reference a ref that does not
                # exist.
                return None
        else:
            return None

    async def resolveRef(  # type: ignore[override]
        self,
        ref: str,
        *,
        expect: Optional[ObjectType] = None,
        short: bool = False,
    ) -> str:
        try:
            if short:
                return await self.low_level.revparse(
                    ref, object_type=expect, short=True
                )
            else:
                return await self.low_level.revparse(ref, object_type=expect)
        except gitaccess.GitReferenceError:
            raise api.repository.InvalidRef(ref)

    async def listRefs(self, *, pattern: Optional[str] = None) -> Collection[str]:
        assert not pattern or not pattern.startswith("-")
        try:
            return await self.low_level.foreachref(pattern=pattern)
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )

    @overload
    async def __revlist(
        self,
        include: Optional[public.Refs],
        exclude: Optional[public.Refs],
        paths: Optional[Iterable[str]],
        min_parents: Optional[int],
        max_parents: Optional[int],
        *,
        count: Literal[True],
    ) -> int:
        ...

    @overload
    async def __revlist(
        self,
        include: Optional[public.Refs],
        exclude: Optional[public.Refs],
        paths: Optional[Iterable[str]],
        min_parents: Optional[int],
        max_parents: Optional[int],
        *,
        count: Literal[False],
    ) -> Sequence[SHA1]:
        ...

    async def __revlist(
        self,
        include: Optional[public.Refs],
        exclude: Optional[public.Refs],
        paths: Optional[Iterable[str]],
        min_parents: Optional[int],
        max_parents: Optional[int],
        *,
        count: bool,
    ) -> Union[int, Sequence[SHA1]]:
        def is_valid_ref(ref: public.Refs) -> Optional[str]:
            if isinstance(ref, (api.commit.Commit, str)):
                ref = str(ref)
                if ref == "--all" or gitaccess.is_sha1(ref):
                    return ref
            return None

        def is_valid_refs(refs: Sequence[str]) -> bool:
            return (
                len(refs) == 1
                if "--all" in refs
                else all(is_valid_ref(ref) for ref in refs)
            )

        if include is None:
            include_refs = []
        elif is_valid_ref(include):
            assert not isinstance(include, Iterable)
            include_refs = [str(include)]
        else:
            assert isinstance(include, Iterable)
            include_refs = [str(ref) for ref in include]
        if exclude is None:
            exclude_refs = []
        elif is_valid_ref(exclude):
            exclude_refs = [str(exclude)]
        else:
            assert isinstance(exclude, Iterable)
            exclude_refs = [str(ref) for ref in exclude]
        assert is_valid_refs(include_refs)
        assert is_valid_refs(exclude_refs)

        try:
            if count:
                return await self.low_level.revlist(
                    include_refs,
                    exclude_refs,
                    count=True,
                    paths=paths,
                    min_parents=min_parents,
                    max_parents=max_parents,
                )
            return await self.low_level.revlist(
                include_refs,
                exclude_refs,
                paths=paths,
                min_parents=min_parents,
                max_parents=max_parents,
            )
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )

    async def countCommits(
        self,
        *,
        include: Optional[public.Refs] = None,
        exclude: Optional[public.Refs] = None,
        paths: Optional[Iterable[str]] = None,
        min_parents: Optional[int] = None,
        max_parents: Optional[int] = None,
    ) -> int:
        return await self.__revlist(
            include, exclude, paths, min_parents, max_parents, count=True
        )

    async def listCommits(
        self,
        *,
        include: Optional[public.Refs] = None,
        exclude: Optional[public.Refs] = None,
        paths: Optional[Iterable[str]] = None,
        min_parents: Optional[int] = None,
        max_parents: Optional[int] = None,
    ) -> Sequence[api.commit.Commit]:
        return await api.commit.fetchMany(
            self,
            sha1s=await self.__revlist(
                include, exclude, paths, min_parents, max_parents, count=False
            ),
        )

    async def mergeBase(self, *commits: api.commit.Commit) -> api.commit.Commit:
        try:
            sha1 = await self.low_level.mergebase(*(commit.sha1 for commit in commits))
        except gitaccess.GitProcessError as error:
            raise api.repository.GitCommandError(
                error.argv, error.returncode, error.stdout, error.stderr
            )
        return await api.commit.fetch(self, sha1=sha1)

    async def protectCommit(self, commit: api.commit.Commit) -> None:
        await self.low_level.updateref(
            "refs/keepalive/" + commit.sha1, new_value=commit.sha1
        )

    async def getFileContents(  # type: ignore[override]
        self,
        *,
        commit: Optional[api.commit.Commit] = None,
        file: Optional[api.file.File] = None,
        sha1: Optional[SHA1] = None,
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
            await self.low_level.fetchone(sha1, wanted_object_type="blob"),
        ).data

    @staticmethod
    async def __loadStatistics(critic: api.critic.Critic) -> None:
        cached_objects = Repository.allCached()

        need_fetch = []
        for repository in cached_objects.values():
            if repository.__statistics is None:
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
                  AND repository=ANY({need_fetch})
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
                  AND repository=ANY({need_fetch})
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
                  AND repository=ANY({need_fetch})
             GROUP BY repository""",
            need_fetch=need_fetch,
        ) as reviews_result:
            async for repository_id, count_reviews in reviews_result:
                reviews[repository_id] = count_reviews

        for repository_id in need_fetch:
            cached_objects[repository_id].__statistics = Statistics(
                commits.get(repository_id, 0),
                branches.get(repository_id, 0),
                reviews.get(repository_id, 0),
            )

    @property
    async def statistics(self) -> PublicType.Statistics:
        if self.__statistics is None:
            await self.__loadStatistics(self.critic)
            assert self.__statistics is not None
        return self.__statistics

    async def __getDefaultEncodings(self, category: str) -> Encodings:
        if category not in self.__default_encodings:
            encodings: Sequence[str]
            encodings, was_defined = await api.repositorysetting.get(
                self.critic, self, "defaultEncodings", category, default=["utf-8"]
            )
            if not was_defined:
                encodings = cast(
                    Sequence[str],
                    await api.systemsetting.get(
                        self.critic, f"repositories.default_encodings.{category}"
                    ),
                )
            self.__default_encodings[category] = Encodings(encodings)
        return self.__default_encodings[category]

    async def __getFileEncodings(self, commit_sha1: Optional[SHA1]) -> FileEncodings:
        async def create() -> FileEncodings:
            return FileEncodings(await self.__getDefaultEncodings("files"))

        if commit_sha1 is None:
            return await create()

        try:
            encodings_sha1 = await self.low_level.revparse(
                f"{commit_sha1}:.critic/encodings"
            )
        except gitaccess.GitReferenceError:
            return await create()
        if encodings_sha1 not in self.__file_encodings:
            encodings_blob = await self.low_level.fetchone(
                encodings_sha1, wanted_object_type="blob"
            )
            try:
                encodings_source = encodings_blob.asBlob().data.decode()
            except UnicodeDecodeError:
                return await create()
            self.__file_encodings[encodings_sha1] = (await create()).read(
                self.__path, commit_sha1, encodings_source
            )
        return self.__file_encodings[encodings_sha1]

    async def getDecode(
        self, commit: Optional[Union[SHA1, api.commit.Commit]] = None
    ) -> public.Decode:
        commit_sha1 = commit.sha1 if isinstance(commit, api.commit.Commit) else commit
        if commit_sha1 not in self.__decode:
            self.__decode[commit_sha1] = Decode(
                await self.__getDefaultEncodings("commits"),
                await self.__getFileEncodings(commit_sha1),
                await self.__getDefaultEncodings("paths"),
            )
        return self.__decode[commit_sha1]

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "name", "path", "ready"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    repository_id: Optional[int],
    name: Optional[str],
    path: Optional[str],
) -> PublicType:
    if repository_id is not None:
        return await Repository.ensureOne(
            repository_id, queries.idFetcher(critic, Repository), public.InvalidId
        )
    if name is not None:
        parameters = dbaccess.parameters(name=name)
    else:
        assert path is not None
        parameters = dbaccess.parameters(path=path)
    try:
        repository = Repository.storeOne(
            await queries.query(critic, **parameters).makeOne(Repository)
        )
    except dbaccess.ZeroRowsInResult:
        if name is not None:
            raise api.repository.InvalidName(value=name)
        assert path is not None
        raise api.repository.InvalidRepositoryPath(path)
    await Repository.checkAccess(repository)
    return repository


@public.fetchAllImpl
async def fetchAll(critic: api.critic.Critic) -> Sequence[PublicType]:
    return await Repository.filterInaccessible(
        Repository.store(await queries.query(critic).make(Repository))
    )


@public.fetchHighlightedImpl
async def fetchHighlighted(
    critic: api.critic.Critic, user: api.user.User
) -> Sequence[PublicType]:
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

    return await Repository.filterInaccessible(
        Repository.store(
            await queries.queryByIds(critic, [*highlighted_ids]).make(Repository)
        )
    )


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
