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
    Optional,
    Tuple,
    Literal,
    Mapping,
    Sequence,
    Iterable,
    Mapping,
    Any,
    Union,
    List,
    Set,
    Dict,
    DefaultDict,
    TypeVar,
    cast,
)

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api


@dataclasses.dataclass(frozen=True)
class DraftChangesImpl:
    author: api.user.User
    is_draft: bool
    reply: Optional[api.reply.Reply] = None
    new_type: Optional[api.comment.CommentType] = None
    new_state: Optional[api.comment.IssueState] = None
    new_location: Optional[api.comment.Location] = None


InternalState = Literal["open", "addressed", "closed"]

WrapperType = api.comment.Comment
ArgumentsType = Tuple[
    int,
    api.comment.CommentType,
    int,
    int,
    int,
    str,
    datetime.datetime,
    api.comment.Side,
    int,
    int,
    int,
    InternalState,
    int,
    int,
    int,
]


class Comment(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.comment.Comment
    table_name = "commentchains"
    column_names = [
        "id",
        "type",
        "review",
        "batch",
        "uid",
        "text",
        "time",
        "origin",
        "file",
        "first_commit",
        "last_commit",
        "state",
        "closed_by",
        "addressed_by",
        "addressed_by_update",
    ]

    # "Closed" is only used in the database, really, the UI has always
    # called it "Resolve" (action) / "Resolved" (state).
    INTERNAL_STATE_MAP: Mapping[api.comment.IssueState, InternalState] = {
        "open": "open",
        "addressed": "addressed",
        "resolved": "closed",
    }
    EXTERNAL_STATE_MAP: Mapping[InternalState, api.comment.IssueState] = {
        "open": "open",
        "addressed": "addressed",
        "closed": "resolved",
    }

    __location: Optional[api.comment.Location]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__type,
            self.__review_id,
            self.__batch_id,
            self.__author_id,
            self.text,
            self.timestamp,
            self.side,
            self.__file_id,
            self.__first_commit_id,
            self.__last_commit_id,
            state,
            self.__resolved_by_id,
            self.__addressed_by_id,
            self.__addressed_by_update_id,
        ) = args

        self.is_draft = self.__batch_id is None
        self.state = Comment.EXTERNAL_STATE_MAP[state]
        self.__location = None

        if self.__type == "issue":
            self.wrapper_class = api.comment.Issue
        else:
            self.wrapper_class = api.comment.Note

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        return await api.review.fetch(critic, self.__review_id)

    async def getRepository(
        self, critic: api.critic.Critic
    ) -> api.repository.Repository:
        return await (await self.getReview(critic)).repository

    async def getAuthor(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__author_id)

    async def __fetchLocation(
        self, critic: api.critic.Critic
    ) -> Optional[api.comment.Location]:
        Lines = Tuple[int, int]

        async def get_lines(sha1: str) -> Lines:
            conditions = ["chain={comment_id}", "sha1={sha1}"]
            if critic.session_type == "user":
                conditions.append("(state!='draft' OR uid={user})")
            async with api.critic.Query[Lines](
                critic,
                f"""SELECT first_line, last_line
                      FROM commentchainlines
                     WHERE {" AND ".join(conditions)}""",
                comment_id=self.id,
                sha1=sha1,
                user=critic.effective_user,
            ) as result:
                return await result.one()

        if self.__file_id is not None:
            repository = await self.getRepository(critic)
            if self.side == "old":
                commit = await api.commit.fetch(repository, self.__first_commit_id)
            else:
                commit = await api.commit.fetch(repository, self.__last_commit_id)
            file_information = await commit.getFileInformation(
                await api.file.fetch(critic, self.__file_id)
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
                side=self.side,
            ).wrap(critic)
        elif self.__first_commit_id is not None:
            repository = await self.getRepository(critic)
            commit = await api.commit.fetch(
                repository, commit_id=self.__first_commit_id
            )
            first_line, last_line = await get_lines(commit.sha1)
            # FIXME: Make commit message comment line numbers one-based too!
            first_line += 1
            last_line += 1
            # FIXME: ... and then delete the above two lines of code.
            return CommitMessageLocation(
                first_line, last_line, repository, self.__first_commit_id
            ).wrap(critic)
        else:
            return None

    async def getLocation(
        self, critic: api.critic.Critic
    ) -> Optional[api.comment.Location]:
        if self.__location is None:
            self.__location = await self.__fetchLocation(critic)
        return self.__location

    async def getAddressedBy(
        self, critic: api.critic.Critic
    ) -> Optional[api.commit.Commit]:
        if self.state != "addressed":
            return None
        repository = await self.getRepository(critic)
        return await api.commit.fetch(repository, self.__addressed_by_id)

    async def getResolvedBy(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.state != "resolved":
            return None
        return await api.user.fetch(critic, self.__resolved_by_id)

    async def getDraftChanges(
        self, critic: api.critic.Critic
    ) -> Optional[api.comment.Comment.DraftChanges]:
        if critic.effective_user.is_anonymous:
            return None
        if self.is_draft:
            # async with critic.query(
            #     """SELECT id, value
            #          FROM commenttextbackups
            #         WHERE uid={user}
            #           AND comment={comment_id}
            #      ORDER BY timestamp DESC""",
            #     user=critic.effective_user,
            #     comment_id=self.id,
            # ) as result:
            #     text_backups = [
            #         api.comment.Comment.DraftChanges.TextBackup(backup_id, value)
            #         for backup_id, value in await result.all()
            #     ]
            return DraftChangesImpl(critic.effective_user, True)
        async with critic.query(
            """SELECT id
                 FROM comments
                WHERE uid={user_id}
                  AND chain={comment_id}
                  AND batch IS NULL""",
            user_id=critic.effective_user.id,
            comment_id=self.id,
        ) as result:
            reply_id = await result.maybe_scalar()
        reply: Optional[api.reply.Reply]
        if reply_id is not None:
            reply = await api.reply.fetch(critic, reply_id)
        else:
            reply = None
        effective_type = self.__type
        new_type = None
        new_state = None
        new_location = None
        async with critic.query(
            """SELECT from_state, to_state, from_type, to_type,
                      from_last_commit, to_last_commit,
                      from_addressed_by, to_addressed_by
                 FROM commentchainchanges
                WHERE uid={user_id}
                  AND chain={comment_id}
                  AND state='draft'""",
            user_id=critic.effective_user.id,
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
                from_last_commit,
                to_last_commit,
                from_addressed_by,
                to_addressed_by,
            ) = row
            if to_type is not None and from_type == self.__type:
                effective_type = new_type = to_type
            if to_state is not None:
                if Comment.EXTERNAL_STATE_MAP[from_state] == self.state:
                    new_state = Comment.EXTERNAL_STATE_MAP[to_state]
            # FIXME: Handle new location.
        if effective_type == "note":
            return DraftChangesImpl(critic.effective_user, False, reply, new_type)
        return DraftChangesImpl(
            critic.effective_user, False, reply, new_type, new_state, new_location
        )

    @staticmethod
    async def refresh(
        critic: api.critic.Critic,
        tables: Set[str],
        cached_comments: Mapping[Any, WrapperType],
    ) -> None:
        if not tables.intersection(("commentchains", "comments")):
            return

        await Comment.updateAll(
            critic,
            f"""SELECT {Comment.columns()}
                  FROM commentchains
                 WHERE {{commentchains.id=object_ids:array}}""",
            cached_comments,
        )


@Comment.cached
async def fetch(critic: api.critic.Critic, comment_id: int) -> WrapperType:
    async with Comment.query(
        critic, ["id={comment_id}", "state!='empty'"], comment_id=comment_id
    ) as result:
        return await Comment.makeOne(critic, result)


@Comment.cachedMany
async def fetchMany(
    critic: api.critic.Critic, comment_ids: Sequence[int]
) -> Sequence[WrapperType]:
    async with Comment.query(
        critic,
        ["id=ANY ({comment_ids})", "state!='empty'"],
        comment_ids=list(comment_ids),
    ) as result:
        return await Comment.make(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    author: Optional[api.user.User],
    comment_type: Optional[api.comment.CommentType],
    state: Optional[api.comment.IssueState],
    location_type: Optional[api.comment.LocationType],
    changeset: Optional[api.changeset.Changeset],
    commit: Optional[api.commit.Commit],
    files: Optional[Iterable[api.file.File]],
    addressed_by: Optional[Union[api.commit.Commit, api.branchupdate.BranchUpdate]],
) -> Sequence[WrapperType]:
    joins = [Comment.table()]
    conditions = [
        # Skip (legacy) deleted comments.
        "commentchains.state!='empty'"
    ]

    if critic.session_type == "user":
        conditions.append(
            "(commentchains.batch IS NOT NULL OR commentchains.uid={user_id})"
        )
    if review:
        conditions.append("commentchains.review={review}")
    if author:
        conditions.append("commentchains.uid={author}")
    if comment_type:
        conditions.append("commentchains.type={comment_type}")
    internal_state: Optional[InternalState]
    if state:
        internal_state = Comment.INTERNAL_STATE_MAP[state]
        conditions.append("commentchains.state={internal_state}")
    else:
        internal_state = None
    if location_type:
        if location_type == "commit-message":
            conditions.extend(
                ["commentchains.file IS NULL", "commentchains.first_commit IS NOT NULL"]
            )
        else:
            conditions.extend(["commentchains.file IS NOT NULL"])
    if changeset is not None:
        joins.extend(
            [
                """JOIN commentchainlines
                     ON (commentchainlines.chain=commentchains.id)""",
                """JOIN changesetfiles
                     ON (changesetfiles.file=commentchains.file AND
                        commentchainlines.sha1 IN (changesetfiles.old_sha1,
                                                   changesetfiles.new_sha1))""",
            ]
        )
        conditions.append("changesetfiles.changeset={changeset}")
        if critic.session_type == "user":
            conditions.append(
                "(commentchainlines.state='current' OR"
                " commentchainlines.uid={user_id})"
            )
    file_ids: Optional[List[int]]
    if files is not None:
        conditions.append("{commentchains.file=file_ids:array}")
        file_ids = [file.id for file in files]
    else:
        file_ids = None
    if addressed_by is not None:
        if isinstance(addressed_by, api.commit.Commit):
            conditions.append("commentchains.addressed_by={addressed_by}")
        else:
            conditions.append("commentchains.addressed_by_update={addressed_by}")

    # Skip batch comments.
    joins.append("LEFT OUTER JOIN batches ON (batches.comment=commentchains.id)")
    conditions.append("batches.id IS NULL")

    async with Comment.query(
        critic,
        f"""SELECT DISTINCT {Comment.columns()}
              FROM {" ".join(joins)}
             WHERE {" AND ".join(conditions)}
          ORDER BY commentchains.id""",
        user_id=critic.effective_user.id,
        review=review,
        author=author,
        comment_type=comment_type,
        state=internal_state,
        changeset=changeset,
        file_ids=file_ids,
        addressed_by=addressed_by,
    ) as comments_result:
        comments = await Comment.make(critic, comments_result)

    if commit is not None:
        comments_by_id = {comment.id: comment for comment in comments}
        comments_by_sha1: DefaultDict[str, Set[WrapperType]] = collections.defaultdict(
            set
        )
        async with api.critic.Query[Tuple[int, str]](
            critic,
            """SELECT chain, sha1
                 FROM commentchainlines
                WHERE {chain=comment_ids:array}""",
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


T = TypeVar("T", bound=api.comment.Location)


class Location(apiobject.APIObject[T, Any, Any]):
    def __init__(self, first_line: int, last_line: int) -> None:
        self.first_line = first_line
        self.last_line = last_line


class CommitMessageLocation(Location[api.comment.CommitMessageLocation]):
    wrapper_class = api.comment.CommitMessageLocation

    def __init__(
        self,
        first_line: int,
        last_line: int,
        repository: api.repository.Repository,
        commit_id: int,
    ) -> None:
        super().__init__(first_line, last_line)
        self.repository = repository
        self.__commit_id = commit_id

    async def getCommit(self, critic: api.critic.Critic) -> api.commit.Commit:
        return await api.commit.fetch(self.repository, self.__commit_id)


def makeCommitMessageLocation(
    critic: api.critic.Critic,
    first_line: int,
    last_line: int,
    commit: api.commit.Commit,
) -> api.comment.CommitMessageLocation:
    max_line = len(commit.message.splitlines())

    if last_line < first_line:
        raise api.comment.InvalidLocation(
            "first_line must be equal to or less than last_line"
        )
    if last_line > max_line:
        raise api.comment.InvalidLocation(
            "last_line must be less than or equal to the number of lines in "
            "the commit message"
        )

    return CommitMessageLocation(
        first_line, last_line, commit.repository, commit.id
    ).wrap(critic)


class FileVersionLocation(Location[api.comment.FileVersionLocation]):
    wrapper_class = api.comment.FileVersionLocation

    def __init__(
        self,
        comment: Optional[Comment],
        first_line: int,
        last_line: int,
        repository: api.repository.Repository,
        file_id: int,
        changeset: api.changeset.Changeset = None,
        first_commit_id: int = None,
        last_commit_id: int = None,
        side: api.comment.Side = None,
        commit: api.commit.Commit = None,
        commit_id: int = None,
        is_translated: bool = False,
    ) -> None:
        super().__init__(first_line, last_line)
        self.comment = comment
        if first_commit_id is not None and first_commit_id == last_commit_id:
            commit_id = last_commit_id
            first_commit_id = last_commit_id = side = None
        self.repository = repository
        self.__file_id = file_id
        self.__changeset = changeset
        self.__first_commit_id = first_commit_id
        self.__last_commit_id = last_commit_id
        self.side = side
        self.__commit = commit
        self.__commit_id = commit_id
        self.is_translated = is_translated

    async def getChangeset(
        self, critic: api.critic.Critic
    ) -> Optional[api.changeset.Changeset]:
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
            critic, from_commit=from_commit, to_commit=to_commit
        )

    async def getCommit(self, critic: api.critic.Critic) -> Optional[api.commit.Commit]:
        if self.__commit:
            return self.__commit
        if self.__commit_id is None:
            return None
        return await api.commit.fetch(self.repository, self.__commit_id)

    async def getFile(self, critic: api.critic.Critic) -> api.file.File:
        return await api.file.fetch(critic, self.__file_id)

    async def getFileInformation(
        self, wrapper: api.comment.FileVersionLocation
    ) -> api.commit.Commit.FileInformation:
        commit = await wrapper.commit
        if commit is None:
            changeset = await wrapper.changeset
            assert changeset
            if self.side == "old":
                commit = await changeset.from_commit
            else:
                commit = await changeset.to_commit
            assert commit
        file_information = await commit.getFileInformation(await wrapper.file)
        assert file_information
        return file_information

    async def translateTo(
        self,
        critic: api.critic.Critic,
        changeset: Optional[api.changeset.Changeset],
        commit: Optional[api.commit.Commit],
    ) -> Optional[api.comment.FileVersionLocation]:
        file = await self.getFile(critic)

        async def translateToCommit(
            target_commit: api.commit.Commit, side: Optional[api.comment.Side]
        ) -> api.comment.FileVersionLocation:
            comment = self.comment
            assert comment
            try:
                file_information = await target_commit.getFileInformation(file)
            except api.commit.NotAFile:
                raise KeyError
            if not file_information:
                raise KeyError
            conditions = ["chain={comment_id}", "sha1={sha1}"]
            if critic.session_type == "user":
                conditions.append("(state='current' OR uid={user})")
            async with critic.query(
                f"""SELECT first_line, last_line
                      FROM commentchainlines
                     WHERE {" AND ".join(conditions)}""",
                comment_id=comment.id,
                sha1=file_information.sha1,
                user=critic.effective_user,
            ) as result:
                try:
                    first_line, last_line = await result.one()
                except result.ZeroRowsInResult:
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
            ).wrap(critic)

        if changeset:
            async with critic.query(
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


async def makeFileVersionLocation(
    critic: api.critic.Critic,
    first_line: int,
    last_line: int,
    file: api.file.File,
    changeset: Optional[api.changeset.Changeset],
    side: Optional[api.comment.Side],
    commit: Optional[api.commit.Commit],
) -> api.comment.FileVersionLocation:
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
        raise api.comment.InvalidLocation(
            "first_line must be equal to or less than last_line"
        )
    if last_line > max_line:
        raise api.comment.InvalidLocation(
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
    ).wrap(critic)
