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

import datetime
import logging
from dataclasses import dataclass
from typing import (
    Callable,
    Collection,
    Tuple,
    Optional,
    Sequence,
    Set,
    FrozenSet,
    Mapping,
)

from .queryhelper import QueryHelper, QueryResult, join

logger = logging.getLogger(__name__)

from critic import api, dbaccess
from critic.api import batch as public
from .apiobject import APIObjectImplWithId


@dataclass
class ModifiedComment:
    comment_id: int
    new_type: Optional[api.comment.CommentType]
    new_state: Optional[api.comment.IssueState]


PublicType = public.Batch
ArgumentsType = Tuple[int, Optional[int], Optional[int], int, int]

UNPUBLISHED_ID = -1


class Batch(PublicType, APIObjectImplWithId, module=public):
    __created_comment_ids: Optional[Sequence[int]]
    __empty_comment_ids: Optional[Sequence[int]]
    __written_reply_ids: Optional[Sequence[int]]
    __empty_reply_ids: Optional[Sequence[int]]
    __modified_comments: Optional[Sequence[ModifiedComment]]
    __reviewed_file_change_ids: Optional[Set[int]]
    __reviewed_file_changes: Optional[
        FrozenSet[api.reviewablefilechange.ReviewableFileChange]
    ]
    __unreviewed_file_change_ids: Optional[Set[int]]
    __unreviewed_file_changes: Optional[
        FrozenSet[api.reviewablefilechange.ReviewableFileChange]
    ]

    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__event_id,
            self.__comment_id,
            self.__review_id,
            self.__author_id,
        ) = args
        self.__created_comment_ids = None
        self.__empty_comment_ids = None
        self.__written_reply_ids = None
        self.__empty_reply_ids = None
        self.__modified_comments = None
        self.__reviewed_file_change_ids = None
        self.__reviewed_file_changes = None
        self.__unreviewed_file_change_ids = None
        self.__unreviewed_file_changes = None
        return self.__id

    def __hash__(self) -> int:
        return hash((self.__id, self.__review_id, self.__author_id))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Batch)
            and self.__id == other.__id
            # The following are for the case of an unpublished batch, where `id`
            # will be the same negative number.
            and self.__review_id == other.__review_id
            and self.__author_id == other.__author_id
        )

    def __repr__(self) -> str:
        if self.is_unpublished:
            return f"Batch(review={self.__review_id}, author={self.__author_id})"
        return f"Batch(id={self.__id})"

    def getCacheKeys(self) -> Collection[object]:
        if self.__id is None:
            return ()
        return (self.__id,)

    @property
    def id(self) -> int:
        return self.__id

    @property
    def is_unpublished(self) -> bool:
        return self.id < 0

    @property
    async def is_empty(self) -> bool:
        await self.loadCommentChanges()
        await self.loadFileChanges()
        return not (
            self.__created_comment_ids
            or self.__written_reply_ids
            or self.__modified_comments
            or self.__reviewed_file_change_ids
            or self.__unreviewed_file_change_ids
        )

    @property
    async def event(self) -> Optional[api.reviewevent.ReviewEvent]:
        if self.__event_id is None:
            return None
        return await api.reviewevent.fetch(self.critic, self.__event_id)

    @property
    async def review(self) -> api.review.Review:
        return await api.review.fetch(self.critic, self.__review_id)

    @property
    async def author(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__author_id)

    @property
    async def timestamp(self) -> Optional[datetime.datetime]:
        return event.timestamp if (event := await self.event) else None

    @property
    async def comment(self) -> Optional[api.comment.Comment]:
        if self.__comment_id is None:
            return None
        return await api.comment.fetch(self.critic, self.__comment_id)

    @property
    async def created_comments(self) -> Collection[api.comment.Comment]:
        if self.__created_comment_ids is None:
            await self.loadCommentChanges()
            assert self.__created_comment_ids is not None
        return set(await api.comment.fetchMany(self.critic, self.__created_comment_ids))

    @property
    async def empty_comments(self) -> Collection[api.comment.Comment]:
        if self.__empty_comment_ids is None:
            await self.loadCommentChanges()
            assert self.__empty_comment_ids is not None
        return set(await api.comment.fetchMany(self.critic, self.__empty_comment_ids))

    @property
    async def written_replies(self) -> Collection[api.reply.Reply]:
        if self.__written_reply_ids is None:
            await self.loadCommentChanges()
            assert self.__written_reply_ids is not None
        return set(await api.reply.fetchMany(self.critic, self.__written_reply_ids))

    @property
    async def empty_replies(self) -> Collection[api.reply.Reply]:
        if self.__empty_reply_ids is None:
            await self.loadCommentChanges()
            assert self.__empty_reply_ids is not None
        return set(await api.reply.fetchMany(self.critic, self.__empty_reply_ids))

    @property
    async def resolved_issues(self) -> Collection[api.comment.Comment]:
        if self.__modified_comments is None:
            await self.loadCommentChanges()
        assert self.__modified_comments is not None
        return set(
            await api.comment.fetchMany(
                self.critic,
                (
                    modified_comment.comment_id
                    for modified_comment in self.__modified_comments
                    if modified_comment.new_state == "resolved"
                ),
            )
        )

    @property
    async def reopened_issues(self) -> Collection[api.comment.Comment]:
        if self.__modified_comments is None:
            await self.loadCommentChanges()
        assert self.__modified_comments is not None
        return set(
            await api.comment.fetchMany(
                self.critic,
                (
                    modified_comment.comment_id
                    for modified_comment in self.__modified_comments
                    if modified_comment.new_state == "open"
                ),
            )
        )

    @property
    async def morphed_comments(
        self,
    ) -> Mapping[api.comment.Comment, api.comment.CommentType]:
        if self.__modified_comments is None:
            await self.loadCommentChanges()
        assert self.__modified_comments is not None
        new_type_by_comment_id = {
            modified_comment.comment_id: modified_comment.new_type
            for modified_comment in self.__modified_comments
            if modified_comment.new_type is not None
        }
        comments = await api.comment.fetchMany(
            self.critic, new_type_by_comment_id.keys()
        )
        return {comment: new_type_by_comment_id[comment.id] for comment in comments}  # type: ignore

    @property
    async def reviewed_file_changes(
        self,
    ) -> Collection[api.reviewablefilechange.ReviewableFileChange]:
        if self.__reviewed_file_changes is None:
            if self.__reviewed_file_change_ids is None:
                await self.loadFileChanges()
                assert self.__reviewed_file_change_ids is not None
            self.__reviewed_file_changes = frozenset(
                await api.reviewablefilechange.fetchMany(
                    self.critic, self.__reviewed_file_change_ids
                )
            )
        return self.__reviewed_file_changes

    @property
    async def unreviewed_file_changes(
        self,
    ) -> Collection[api.reviewablefilechange.ReviewableFileChange]:
        if self.__unreviewed_file_changes is None:
            if self.__unreviewed_file_change_ids is None:
                await self.loadFileChanges()
                assert self.__unreviewed_file_change_ids is not None
            self.__unreviewed_file_changes = frozenset(
                await api.reviewablefilechange.fetchMany(
                    self.critic, self.__unreviewed_file_change_ids
                )
            )
        return self.__unreviewed_file_changes

    def __queryCondition(self) -> str:
        return "batch IS NULL" if self.is_unpublished else "batch={batch_id}"

    async def loadCommentChanges(self) -> None:
        condition = self.__queryCondition()

        self.__created_comment_ids = []
        self.__empty_comment_ids = []
        async with api.critic.Query[Tuple[int, str]](
            self.critic,
            f"""SELECT id, text
                  FROM comments
                 WHERE review={{review_id}}
                   AND author={{author_id}}
                   AND {condition}""",
            review_id=self.__review_id,
            author_id=self.__author_id,
            batch_id=self.id,
        ) as result:
            async for comment_id, text in result:
                if comment_id == self.__comment_id:
                    continue
                if text.strip():
                    self.__created_comment_ids.append(comment_id)
                else:
                    self.__empty_comment_ids.append(comment_id)

        self.__written_reply_ids = []
        self.__empty_reply_ids = []
        async with api.critic.Query[Tuple[int, str]](
            self.critic,
            f"""SELECT replies.id, replies.text
                  FROM replies
                  JOIN comments ON (comments.id=replies.comment)
                 WHERE comments.review={{review_id}}
                   AND replies.author={{author_id}}
                   AND replies.{condition}""",
            review_id=self.__review_id,
            author_id=self.__author_id,
            batch_id=self.id,
        ) as result:
            async for reply_id, text in result:
                if text.strip():
                    self.__written_reply_ids.append(reply_id)
                else:
                    self.__empty_reply_ids.append(reply_id)

        self.__modified_comments = []
        async with api.critic.Query[
            Tuple[int, api.comment.CommentType, api.comment.IssueState]
        ](
            self.critic,
            """SELECT comments.id, to_type, to_state
                 FROM comments
                 JOIN commentchanges
                      ON (commentchanges.comment=comments.id)
                WHERE comments.review={review_id}
                  AND commentchanges.author={author_id}
                  AND (
                    commentchanges.state='performed'
                    OR COALESCE(
                         commentchanges.from_state, comments.issue_state
                       )=comments.issue_state
                    OR COALESCE(
                         commentchanges.from_type, comments.type
                       )=comments.type
                  )
                  AND commentchanges."""
            + condition,
            review_id=self.__review_id,
            author_id=self.__author_id,
            batch_id=self.id,
        ) as modified_comments_result:
            async for comment_id, new_type, new_state in modified_comments_result:
                self.__modified_comments.append(
                    ModifiedComment(comment_id, new_type, new_state)
                )

    async def loadFileChanges(self) -> None:
        condition = self.__queryCondition()

        async with api.critic.Query[Tuple[int, bool]](
            self.critic,
            """SELECT ruf.file, rufc.to_reviewed
                 FROM reviewfiles AS rf
                 JOIN reviewuserfiles AS ruf ON (
                        ruf.file=rf.id
                      )
                 JOIN reviewuserfilechanges AS rufc ON (
                        rufc.file=rf.id AND
                        rufc.uid=ruf.uid
                      )
                WHERE rf.review={review_id}
                  AND ruf.uid={author_id}
                  AND (rufc.state='performed' OR
                       rufc.to_reviewed!=ruf.reviewed)
                  AND rufc."""
            + condition,
            review_id=self.__review_id,
            author_id=self.__author_id,
            batch_id=self.id,
        ) as result:
            rows = await result.all()
            logger.debug("loadFileChanges: rows=%r", rows)

        self.__reviewed_file_change_ids = set(
            filechange_id for filechange_id, to_reviewed in rows if to_reviewed
        )
        self.__unreviewed_file_change_ids = set(
            filechange_id for filechange_id, to_reviewed in rows if not to_reviewed
        )

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "event",
    "comment",
    "reviewevents.review",
    "reviewevents.uid",
    default_joins=[join(reviewevents=["batches.event=reviewevents.id"])],
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    batch_id: Optional[int],
    event: Optional[api.reviewevent.ReviewEvent],
) -> PublicType:
    if batch_id is not None:
        condition = "batches.id={batch_id}"
    else:
        condition = "batches.event={event}"
    try:
        return Batch.storeOne(
            await queries.query(
                critic, condition, batch_id=batch_id, event=event
            ).makeOne(Batch),
        )
    except dbaccess.ZeroRowsInResult:
        if batch_id is not None:
            raise api.batch.InvalidId(value=batch_id)
        raise api.batch.InvalidEvent(value=event)


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    author: Optional[api.user.User],
) -> Sequence[PublicType]:
    conditions = ["TRUE"]
    if review or author:
        if review:
            conditions.append("review={review}")
        if author:
            conditions.append("uid={author}")
    return Batch.store(
        await queries.query(
            critic,
            *conditions,
            review=review,
            author=author,
        ).make(Batch),
    )


@public.fetchUnpublishedImpl
async def fetchUnpublished(
    review: api.review.Review, author: Optional[api.user.User]
) -> PublicType:
    if author is None:
        author = review.critic.effective_user
    return Batch(review.critic, (UNPUBLISHED_ID, None, None, review.id, author.id))
