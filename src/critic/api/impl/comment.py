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

import collections
import dataclasses
import datetime
import logging
from typing import (
    Callable,
    Optional,
    Tuple,
    Sequence,
    Iterable,
    Union,
    List,
    Set,
    Dict,
    DefaultDict,
    TypeVar,
    cast,
)

logger = logging.getLogger(__name__)

from critic import api
from critic.api import comment as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult, join, left_outer_join


@dataclasses.dataclass(frozen=True)
class DraftChangesImpl:
    __author: api.user.User
    __is_draft: bool
    __reply: Optional[api.reply.Reply] = None
    __new_type: Optional[public.CommentType] = None
    __new_state: Optional[public.IssueState] = None
    __new_location: Optional[public.Location] = None

    @property
    def author(self) -> api.user.User:
        return self.__author

    @property
    def is_draft(self) -> bool:
        return self.__is_draft

    @property
    def reply(self) -> Optional[api.reply.Reply]:
        return self.__reply

    @property
    def new_type(self) -> Optional[public.CommentType]:
        return self.__new_type

    @property
    def new_state(self) -> Optional[public.IssueState]:
        return self.__new_state

    @property
    def new_location(self) -> Optional[public.Location]:
        return self.__new_location


PublicType = public.Comment
ArgumentsType = Tuple[
    int,
    public.CommentType,
    int,
    int,
    int,
    str,
    datetime.datetime,
    public.Side,
    int,
    int,
    int,
    public.IssueState,
    int,
    int,
]


class Comment(PublicType, APIObjectImplWithId, module=public):
    wrapper_class = public.Comment
    table_name = "comments"
    column_names = [
        "id",
        "type",
        "review",
        "batch",
        "author",
        "text",
        "time",
        "side",
        "file",
        "first_commit",
        "last_commit",
        "issue_state",
        "closed_by",
        "addressed_by",
    ]

    __location: Optional[public.Location]
    __side: public.Side

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__type,
            self.__review_id,
            self.__batch_id,
            self.__author_id,
            self.__text,
            self.__timestamp,
            self.__side,
            self.__file_id,
            self.__first_commit_id,
            self.__last_commit_id,
            self.__issue_state,
            *_,
        ) = args

        self.__location = None
        return self.__id

    @classmethod
    def getCacheCategory(cls) -> str:
        return "Comment"

    @property
    def id(self) -> int:
        return self.__id

    @property
    def is_draft(self) -> bool:
        return self.__batch_id is None

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def author(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__author_id)

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    @property
    async def repository(self) -> api.repository.Repository:
        return await (await self.review).repository

    async def __fetchLocation(self) -> Optional[public.Location]:
        Lines = Tuple[int, int]

        async def get_lines(sha1: str) -> Lines:
            conditions = ["comment={comment_id}", "sha1={sha1}"]
            if self.critic.session_type == "user":
                conditions.append("(state!='draft' OR author={user})")
            async with api.critic.Query[Lines](
                self.critic,
                f"""SELECT first_line, last_line
                      FROM commentlines
                     WHERE {" AND ".join(conditions)}""",
                comment_id=self.id,
                sha1=sha1,
                user=self.critic.effective_user,
            ) as result:
                return await result.one()

        if self.__file_id is not None:
            repository = await self.repository
            if self.__side == "old":
                commit = await api.commit.fetch(repository, self.__first_commit_id)
            else:
                commit = await api.commit.fetch(repository, self.__last_commit_id)
            file_information = await commit.getFileInformation(
                await api.file.fetch(self.critic, self.__file_id)
            )
            assert file_information
            first_line, last_line = await get_lines(file_information.sha1)
            return FileVersionLocation(
                self,
                first_line,
                last_line,
                repository,
                self.__file_id,
                first_commit_id=self.__first_commit_id,
                last_commit_id=self.__last_commit_id,
                side=self.__side,
            )
        elif self.__first_commit_id is not None:
            repository = await self.repository
            commit = await api.commit.fetch(repository, self.__first_commit_id)
            first_line, last_line = await get_lines(commit.sha1)
            # FIXME: Make commit message comment line numbers one-based too!
            first_line += 1
            last_line += 1
            # FIXME: ... and then delete the above two lines of code.
            return CommitMessageLocation(
                first_line, last_line, repository, self.__first_commit_id
            )
        else:
            return None

    @property
    async def location(self) -> Optional[public.Location]:
        if self.__location is None:
            self.__location = await self.__fetchLocation()
        return self.__location

    @property
    def text(self) -> str:
        return self.__text

    async def getDraftChanges(self) -> Optional[DraftChangesImpl]:
        author = self.critic.effective_user
        if author.is_anonymous:
            return None
        if self.is_draft:
            # async with critic.query(
            #     """SELECT id, value
            #          FROM commenttextbackups
            #         WHERE author={user}
            #           AND comment={comment_id}
            #      ORDER BY timestamp DESC""",
            #     user=critic.effective_user,
            #     comment_id=self.id,
            # ) as result:
            #     text_backups = [
            #         public.Comment.DraftChanges.TextBackup(backup_id, value)
            #         for backup_id, value in await result.all()
            #     ]
            return DraftChangesImpl(author, True)
        async with api.critic.Query[int](
            self.critic,
            """SELECT id
                 FROM replies
                WHERE author={user_id}
                  AND comment={comment_id}
                  AND batch IS NULL""",
            user_id=author.id,
            comment_id=self.id,
        ) as draft_reply_result:
            reply_id = await draft_reply_result.maybe_scalar()
        reply: Optional[api.reply.Reply]
        if reply_id is not None:
            reply = await api.reply.fetch(self.critic, reply_id)
        else:
            reply = None
        effective_type = self.__type
        new_type = None
        new_state = None
        new_location = None
        async with api.critic.Query[
            Tuple[
                public.IssueState,
                public.IssueState,
                public.CommentType,
                public.CommentType,
                int,
                int,
                int,
                int,
            ]
        ](
            self.critic,
            """SELECT from_state, to_state, from_type, to_type,
                      from_last_commit, to_last_commit,
                      from_addressed_by, to_addressed_by
                 FROM commentchanges
                WHERE author={user_id}
                  AND comment={comment_id}
                  AND state='draft'""",
            user_id=author.id,
            comment_id=self.id,
        ) as result:
            row = await result.maybe_one()
        if not row:
            if reply is None:
                return None
        else:
            (
                from_state,
                to_state,
                from_type,
                to_type,
                from_last_commit,  # type: ignore
                to_last_commit,  # type: ignore
                from_addressed_by,  # type: ignore
                to_addressed_by,  # type: ignore
            ) = row
            if to_type is not None and from_type == self.__type:
                effective_type = new_type = to_type
            if to_state is not None:
                if from_state == self.__issue_state:
                    new_state = to_state
            # FIXME: Handle new location.
        if effective_type == "note":
            return DraftChangesImpl(author, False, reply, new_type)
        return DraftChangesImpl(author, False, reply, new_type, new_state, new_location)

    @property
    async def draft_changes(self) -> Optional[public.Comment.DraftChanges]:
        return await self.getDraftChanges()

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "type",
    "review",
    "batch",
    "author",
    "text",
    "time",
    "side",
    "file",
    "first_commit",
    "last_commit",
    "issue_state",
    "closed_by",
    "addressed_by",
)


class Issue(public.Issue, Comment, module=public):
    def update(self, args: ArgumentsType) -> int:
        self.__state = cast(public.IssueState, args[-3])
        self.__resolved_by_id = cast(Optional[int], args[-2])
        self.__addressed_by_id = cast(Optional[int], args[-1])
        return super().update(args)

    @property
    def type(self) -> public.CommentType:
        return "issue"

    @property
    def state(self) -> public.IssueState:
        return self.__state

    @property
    async def addressed_by(self) -> Optional[api.commit.Commit]:
        if self.state != "addressed":
            return None
        assert self.__addressed_by_id is not None
        return await api.commit.fetch(await self.repository, self.__addressed_by_id)

    @property
    async def resolved_by(self) -> Optional[api.user.User]:
        if self.state != "resolved":
            return None
        assert self.__resolved_by_id is not None
        return await api.user.fetch(self.critic, self.__resolved_by_id)

    @property
    async def draft_changes(self) -> Optional[public.Issue.DraftChanges]:
        return await self.getDraftChanges()


class Note(public.Note, Comment, module=public):
    @property
    def type(self) -> public.CommentType:
        return "note"


def makeComment(critic: api.critic.Critic, args: ArgumentsType) -> Comment:
    comment_type = args[1]
    return Issue(critic, args) if comment_type == "issue" else Note(critic, args)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, comment_id: int) -> PublicType:
    return await Comment.ensureOne(
        comment_id,
        queries.idFetcher(critic, makeComment),
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, comment_ids: Sequence[int]
) -> Sequence[PublicType]:
    return await Comment.ensure(
        comment_ids,
        queries.idsFetcher(critic, makeComment),
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    author: Optional[api.user.User],
    comment_type: Optional[public.CommentType],
    issue_state: Optional[public.IssueState],
    location_type: Optional[public.LocationType],
    changeset: Optional[api.changeset.Changeset],
    commit: Optional[api.commit.Commit],
    files: Optional[Iterable[api.file.File]],
    addressed_by: Optional[Union[api.commit.Commit, api.branchupdate.BranchUpdate]],
) -> Sequence[PublicType]:
    joins = []
    conditions = []

    if critic.session_type == "user":
        conditions.append("comments.batch IS NOT NULL OR comments.author={user_id}")
    if review:
        conditions.append("comments.review={review}")
    if author:
        conditions.append("comments.author={author}")
    if comment_type:
        conditions.append("comments.type={comment_type}")
    if issue_state:
        conditions.extend(
            ["comments.type='issue'", "comments.issue_state={issue_state}"]
        )
    if location_type:
        if location_type == "commit-message":
            conditions.extend(
                ["comments.file IS NULL", "comments.first_commit IS NOT NULL"]
            )
        else:
            conditions.extend(["comments.file IS NOT NULL"])
    if changeset is not None:
        joins.extend(
            [
                join(commentlines=["commentlines.comment=comments.id"]),
                join(
                    changesetfiles=[
                        "changesetfiles.file=comments.file",
                        """
                        commentlines.sha1 IN (
                            changesetfiles.old_sha1,
                            changesetfiles.new_sha1
                        )
                        """,
                    ],
                ),
            ]
        )
        conditions.append("changesetfiles.changeset={changeset}")
        if critic.session_type == "user":
            conditions.append(
                "(commentlines.state='current' OR" " commentlines.author={user_id})"
            )
    file_ids: Optional[List[int]]
    if files is not None:
        conditions.append("{comments.file=file_ids:array}")
        file_ids = [file.id for file in files]
    else:
        file_ids = None
    if addressed_by is not None:
        if isinstance(addressed_by, api.commit.Commit):
            conditions.append("comments.addressed_by={addressed_by}")
        else:
            conditions.append("comments.addressed_by_update={addressed_by}")

    # Skip batch comments.
    joins.append(left_outer_join(batches=["batches.comment=comments.id"]))
    conditions.append("batches.id IS NULL")

    comments = Comment.store(
        await queries.query(
            critic,
            queries.formatQuery(*conditions, joins=joins),
            user_id=critic.effective_user.id,
            review=review,
            author=author,
            comment_type=comment_type,
            issue_state=issue_state,
            changeset=changeset,
            file_ids=file_ids,
            addressed_by=addressed_by,
        ).make(makeComment)
    )

    if commit is not None:
        comments_by_id = {comment.id: comment for comment in comments}
        comments_by_sha1: DefaultDict[str, Set[PublicType]] = collections.defaultdict(
            set
        )
        async with api.critic.Query[Tuple[int, str]](
            critic,
            """SELECT comment, sha1
                 FROM commentlines
                WHERE comment=ANY({comment_ids})""",
            comment_ids=list(comments_by_id.keys()),
        ) as file_versions_result:
            async for comment_id, sha1 in file_versions_result:
                comments_by_sha1[sha1].add(comments_by_id[comment_id])
        file_versions_cache: Dict[
            api.file.File, Optional[api.commit.Commit.FileInformation]
        ] = {}
        filtered_comments = []
        for comment in comments:
            location = await comment.location
            if not location:
                continue
            if location.type == "commit-message":
                if location.as_commit_message.commit == commit:
                    filtered_comments.append(comment)
                continue
            file = await location.as_file_version.file
            if file not in file_versions_cache:
                try:
                    file_information = await commit.getFileInformation(file)
                except api.commit.NotAFile:
                    file_information = None
                file_versions_cache[file] = file_information
            else:
                file_information = file_versions_cache[file]
            if file_information is not None:
                if comment in comments_by_sha1.get(file_information.sha1, ()):
                    filtered_comments.append(comment)
        return filtered_comments
    return comments


T = TypeVar("T", bound=public.Location)


class Location(public.Location):
    def __init__(
        self, critic: api.critic.Critic, first_line: int, last_line: int
    ) -> None:
        self.critic = critic
        self.__first_line = first_line
        self.__last_line = last_line

    @property
    def first_line(self) -> int:
        return self.__first_line

    @property
    def last_line(self) -> int:
        return self.__last_line


class CommitMessageLocation(Location, public.CommitMessageLocation):
    wrapper_class = public.CommitMessageLocation

    def __init__(
        self,
        first_line: int,
        last_line: int,
        repository: api.repository.Repository,
        commit_id: int,
    ) -> None:
        Location.__init__(self, repository.critic, first_line, last_line)
        self.__repository = repository
        self.__commit_id = commit_id

    @property
    async def commit(self) -> api.commit.Commit:
        return await api.commit.fetch(self.__repository, self.__commit_id)


@public.makeCommitMessageLocationImpl
def makeCommitMessageLocation(
    first_line: int,
    last_line: int,
    commit: api.commit.Commit,
) -> public.CommitMessageLocation:
    max_line = len(commit.message.splitlines())

    if last_line < first_line:
        raise public.InvalidLocation(
            "first_line must be equal to or less than last_line"
        )
    if last_line > max_line:
        raise public.InvalidLocation(
            "last_line must be less than or equal to the number of lines in "
            "the commit message"
        )

    return CommitMessageLocation(first_line, last_line, commit.repository, commit.id)


class FileVersionLocation(Location, public.FileVersionLocation):
    def __init__(
        self,
        comment: Optional[Comment],
        first_line: int,
        last_line: int,
        repository: api.repository.Repository,
        file_id: int,
        changeset: Optional[api.changeset.Changeset] = None,
        first_commit_id: Optional[int] = None,
        last_commit_id: Optional[int] = None,
        side: Optional[public.Side] = None,
        commit: Optional[api.commit.Commit] = None,
        commit_id: Optional[int] = None,
        is_translated: bool = False,
    ) -> None:
        Location.__init__(self, repository.critic, first_line, last_line)
        self.comment = comment
        if first_commit_id is not None and first_commit_id == last_commit_id:
            commit_id = last_commit_id
            first_commit_id = last_commit_id = side = None
        self.repository = repository
        self.__file_id = file_id
        self.__changeset = changeset
        self.__first_commit_id = first_commit_id
        self.__last_commit_id = last_commit_id
        self.__side = side
        self.__commit = commit
        self.__commit_id = commit_id
        self.__is_translated = is_translated

    @property
    async def changeset(self) -> Optional[api.changeset.Changeset]:
        if self.__changeset:
            return self.__changeset
        if self.side is None:
            # Comment was made while looking at a single version of the file,
            # not while looking at a diff where the file was modified.
            return None
        from_commit_id = self.__first_commit_id
        assert from_commit_id
        to_commit_id = self.__last_commit_id
        assert to_commit_id
        from_commit = await api.commit.fetch(self.repository, from_commit_id)
        to_commit = await api.commit.fetch(self.repository, to_commit_id)
        return await api.changeset.fetch(
            self.critic, from_commit=from_commit, to_commit=to_commit
        )

    @property
    def side(self) -> Optional[public.Side]:
        return self.__side

    @property
    async def commit(self) -> Optional[api.commit.Commit]:
        if self.__commit:
            return self.__commit
        if self.__commit_id is None:
            return None
        return await api.commit.fetch(self.repository, self.__commit_id)

    @property
    async def file(self) -> api.file.File:
        return await api.file.fetch(self.critic, self.__file_id)

    @property
    async def file_information(self) -> api.commit.Commit.FileInformation:
        commit = await self.commit
        if commit is None:
            changeset = await self.changeset
            assert changeset
            if self.side == "old":
                commit = await changeset.from_commit
            else:
                commit = await changeset.to_commit
            assert commit
        file_information = await commit.getFileInformation(await self.file)
        assert file_information
        return file_information

    @property
    def is_translated(self) -> bool:
        return self.__is_translated

    async def translateTo(  # type: ignore[overload]
        self,
        *,
        changeset: Optional[api.changeset.Changeset] = None,
        commit: Optional[api.commit.Commit] = None,
    ) -> Optional[public.FileVersionLocation]:
        file = await self.file

        async def translateToCommit(
            target_commit: api.commit.Commit, side: Optional[public.Side]
        ) -> public.FileVersionLocation:
            comment = self.comment
            assert comment
            try:
                file_information = await target_commit.getFileInformation(file)
            except api.commit.NotAFile:
                raise KeyError
            if not file_information:
                raise KeyError
            conditions = ["comment={comment_id}", "sha1={sha1}"]
            if self.critic.session_type == "user":
                conditions.append("(state='current' OR author={user})")
            async with api.critic.Query[Tuple[int, int]](
                self.critic,
                f"""SELECT first_line, last_line
                      FROM commentlines
                     WHERE {" AND ".join(conditions)}""",
                comment_id=comment.id,
                sha1=file_information.sha1,
                user=self.critic.effective_user,
            ) as lines_result:
                try:
                    first_line, last_line = await lines_result.one()
                except lines_result.ZeroRowsInResult:
                    raise KeyError
            return FileVersionLocation(
                comment,
                first_line,
                last_line,
                self.repository,
                self.__file_id,
                changeset=changeset,
                side=side,
                commit=commit,
                is_translated=True,
            )

        if changeset:
            async with api.critic.Query[int](
                self.critic,
                """SELECT 1
                     FROM changesetfiles
                    WHERE changeset={changeset}
                      AND file={file}""",
                changeset=changeset,
                file=file,
            ) as result:
                if await result.empty():
                    return None
            try:
                return await translateToCommit(await changeset.to_commit, "new")
            except KeyError:
                pass
            from_commit = await changeset.from_commit
            if from_commit:
                try:
                    return await translateToCommit(from_commit, "old")
                except KeyError:
                    pass
        else:
            assert commit
            try:
                return await translateToCommit(commit, None)
            except KeyError:
                pass

        return None


@public.makeFileVersionLocationImpl
async def makeFileVersionLocation(
    first_line: int,
    last_line: int,
    file: api.file.File,
    changeset: Optional[api.changeset.Changeset],
    side: Optional[public.Side],
    commit: Optional[api.commit.Commit],
) -> public.FileVersionLocation:
    if changeset is not None:
        repository = await changeset.repository
        if side == "old":
            check_commit = await changeset.from_commit
        else:
            check_commit = await changeset.to_commit
    else:
        assert commit
        repository = commit.repository
        check_commit = commit

    assert check_commit
    file_lines = await check_commit.getFileLines(file)
    assert file_lines is not None
    max_line = len(file_lines)

    if last_line < first_line:
        raise public.InvalidLocation(
            "first_line must be equal to or less than last_line"
        )
    if last_line > max_line:
        raise public.InvalidLocation(
            "last_line must be less than or equal to the number of lines in "
            "the file version"
        )

    return FileVersionLocation(
        None,
        first_line,
        last_line,
        repository,
        file.id,
        changeset=changeset,
        side=side,
        commit=commit,
    )
