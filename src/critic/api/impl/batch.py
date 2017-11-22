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
from typing import Tuple, Optional, Sequence, Set, FrozenSet, Mapping, List

logger = logging.getLogger(__name__)

from critic import api
from . import apiobject


@dataclass
class ModifiedComment:
    comment_id: int
    new_type: Optional[api.comment.CommentType]
    new_state: Optional[api.comment.IssueState]


WrapperType = api.batch.Batch
ArgumentsType = Tuple[Optional[int], Optional[int], Optional[int]]


class Batch(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.batch.Batch

    table_name = "batches"
    column_names = ["id", "event", "comment"]

    __created_comment_ids: Optional[Sequence[int]]
    __written_reply_ids: Optional[Sequence[int]]
    __modified_comments: Optional[Sequence[ModifiedComment]]
    __reviewed_file_change_ids: Optional[Set[int]]
    __reviewed_file_changes: Optional[
        FrozenSet[api.reviewablefilechange.ReviewableFileChange]
    ]
    __unreviewed_file_change_ids: Optional[Set[int]]
    __unreviewed_file_changes: Optional[
        FrozenSet[api.reviewablefilechange.ReviewableFileChange]
    ]

    def __init__(
        self,
        args: ArgumentsType = (None, None, None),
        *,
        review: api.review.Review = None,
        author: api.user.User = None,
    ) -> None:
        (self.id, self.__event_id, self.__comment_id) = args
        self.__review_id = review.id if review else None
        self.__author_id = author.id if author else None
        self.__created_comment_ids = None
        self.__written_reply_ids = None
        self.__modified_comments = None
        self.__reviewed_file_change_ids = None
        self.__reviewed_file_changes = None
        self.__unreviewed_file_change_ids = None
        self.__unreviewed_file_changes = None

    def __hash__(self) -> int:
        return hash((self.id, self.__review_id, self.__author_id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Batch):
            return False
        if (self.id is None) != (other.id is None):
            return False
        if self.id is not None:
            return self.id == other.id
        return (
            self.__review_id == other.__review_id
            and self.__author_id == other.__author_id
        )

    async def isEmpty(self, critic: api.critic.Critic) -> bool:
        await self.loadCommentChanges(critic)
        await self.loadFileChanges(critic)
        return not (
            self.__created_comment_ids
            or self.__written_reply_ids
            or self.__modified_comments
            or self.__reviewed_file_change_ids
            or self.__unreviewed_file_change_ids
        )

    async def getEvent(
        self, critic: api.critic.Critic
    ) -> Optional[api.reviewevent.ReviewEvent]:
        if self.__event_id is None:
            return None
        return await api.reviewevent.fetch(critic, self.__event_id)

    async def getReview(self, critic: api.critic.Critic) -> api.review.Review:
        if self.__event_id is not None:
            event = await self.getEvent(critic)
            assert event
            return await event.review
        assert self.__review_id is not None
        return await api.review.fetch(critic, self.__review_id)

    async def getAuthor(self, critic: api.critic.Critic) -> api.user.User:
        if self.__event_id is not None:
            event = await self.getEvent(critic)
            assert event
            author = await event.user
            # Event's can be author-less, but not events of "batch" type, like this one.
            assert author
            return author
        assert self.__author_id is not None
        return await api.user.fetch(critic, self.__author_id)

    async def getTimestamp(
        self, critic: api.critic.Critic
    ) -> Optional[datetime.datetime]:
        if self.__event_id is not None:
            event = await self.getEvent(critic)
            assert event
            return event.timestamp
        return None

    async def getComment(
        self, critic: api.critic.Critic
    ) -> Optional[api.comment.Comment]:
        if self.__comment_id is None:
            return None
        return await api.comment.fetch(critic, self.__comment_id)

    async def getCreatedComments(
        self, critic: api.critic.Critic
    ) -> Set[api.comment.Comment]:
        if self.__created_comment_ids is None:
            await self.loadCommentChanges(critic)
            assert self.__created_comment_ids
        return set(await api.comment.fetchMany(critic, self.__created_comment_ids))

    async def getWrittenReplies(
        self, critic: api.critic.Critic
    ) -> Set[api.reply.Reply]:
        if self.__written_reply_ids is None:
            await self.loadCommentChanges(critic)
            assert self.__written_reply_ids
        return set(await api.reply.fetchMany(critic, self.__written_reply_ids))

    async def getResolvedIssues(
        self, critic: api.critic.Critic
    ) -> Set[api.comment.Comment]:
        if self.__modified_comments is None:
            await self.loadCommentChanges(critic)
        assert self.__modified_comments is not None
        return set(
            await api.comment.fetchMany(
                critic,
                (
                    modified_comment.comment_id
                    for modified_comment in self.__modified_comments
                    if modified_comment.new_state == "closed"
                ),
            )
        )

    async def getReopenedIssues(
        self, critic: api.critic.Critic
    ) -> Set[api.comment.Comment]:
        if self.__modified_comments is None:
            await self.loadCommentChanges(critic)
        assert self.__modified_comments is not None
        return set(
            await api.comment.fetchMany(
                critic,
                (
                    modified_comment.comment_id
                    for modified_comment in self.__modified_comments
                    if modified_comment.new_state == "open"
                ),
            )
        )

    async def getMorphedComments(
        self, critic: api.critic.Critic
    ) -> Mapping[api.comment.Comment, api.comment.CommentType]:
        if self.__modified_comments is None:
            await self.loadCommentChanges(critic)
        assert self.__modified_comments is not None
        new_type_by_comment_id = {
            modified_comment.comment_id: modified_comment.new_type
            for modified_comment in self.__modified_comments
            if modified_comment.new_type is not None
        }
        comments = await api.comment.fetchMany(critic, new_type_by_comment_id.keys())
        return {comment: new_type_by_comment_id[comment.id] for comment in comments}

    async def getReviewedFileChanges(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.reviewablefilechange.ReviewableFileChange]:
        if self.__reviewed_file_changes is None:
            if self.__reviewed_file_change_ids is None:
                await self.loadFileChanges(critic)
                assert self.__reviewed_file_change_ids
            self.__reviewed_file_changes = frozenset(
                await api.reviewablefilechange.fetchMany(
                    critic, self.__reviewed_file_change_ids
                )
            )
        return self.__reviewed_file_changes

    async def getUnreviewedFileChanges(
        self, critic: api.critic.Critic
    ) -> FrozenSet[api.reviewablefilechange.ReviewableFileChange]:
        if self.__unreviewed_file_changes is None:
            if self.__unreviewed_file_change_ids is None:
                await self.loadFileChanges(critic)
                assert self.__unreviewed_file_change_ids
            self.__unreviewed_file_changes = frozenset(
                await api.reviewablefilechange.fetchMany(
                    critic, self.__unreviewed_file_change_ids
                )
            )
        return self.__unreviewed_file_changes

    async def __getReviewAndAuthorIds(
        self, critic: api.critic.Critic
    ) -> Tuple[int, int]:
        if self.__event_id is None:
            assert self.__review_id is not None and self.__author_id is not None
            return (self.__review_id, self.__author_id)
        review = await self.getReview(critic)
        author = await self.getAuthor(critic)
        author_id = author.id
        assert author_id is not None  # The author will be a regular user.
        return (review.id, author_id)

    def __queryCondition(self) -> str:
        return "batch IS NULL" if self.id is None else "batch={batch_id}"

    async def loadCommentChanges(self, critic: api.critic.Critic) -> None:
        review_id, author_id = await self.__getReviewAndAuthorIds(critic)
        condition = self.__queryCondition()

        async with critic.query(
            f"""SELECT id
                  FROM commentchains
                 WHERE review={{review_id}}
                   AND state!='empty'
                   AND uid={{author_id}}
                   AND {condition}""",
            review_id=review_id,
            author_id=author_id,
            batch_id=self.id,
        ) as result:
            self.__created_comment_ids = [
                comment_id
                for comment_id in await result.scalars()
                if comment_id != self.__comment_id
            ]

        async with critic.query(
            f"""SELECT comments.id
                  FROM commentchains
                  JOIN comments ON (comments.chain=commentchains.id)
                 WHERE commentchains.review={{review_id}}
                   AND commentchains.state!='empty'
                   AND comments.uid={{author_id}}
                   AND comments.{condition}""",
            review_id=review_id,
            author_id=author_id,
            batch_id=self.id,
        ) as result:
            self.__written_reply_ids = await result.scalars()

        self.__modified_comments = []
        async with critic.query(
            """SELECT commentchains.id, to_type, to_state
                 FROM commentchains
                 JOIN commentchainchanges
                      ON (commentchainchanges.chain=commentchains.id)
                WHERE commentchains.review={review_id}
                  AND commentchains.state!='empty'
                  AND commentchainchanges.uid={author_id}
                  AND (
                    commentchainchanges.state='performed'
                    OR COALESCE(
                         commentchainchanges.from_state, commentchains.state
                       )=commentchains.state
                    OR COALESCE(
                         commentchainchanges.from_type, commentchains.type
                       )=commentchains.type
                  )
                  AND commentchainchanges."""
            + condition,
            review_id=review_id,
            author_id=author_id,
            batch_id=self.id,
        ) as result:
            async for comment_id, new_type, new_state in result:
                self.__modified_comments.append(
                    ModifiedComment(comment_id, new_type, new_state)
                )

    async def loadFileChanges(self, critic: api.critic.Critic) -> None:
        review_id, author_id = await self.__getReviewAndAuthorIds(critic)
        condition = self.__queryCondition()

        async with api.critic.Query[Tuple[int, bool]](
            critic,
            """SELECT rf.id, rfc.to_reviewed
                 FROM reviewfiles AS rf
                 JOIN reviewuserfiles AS ruf ON (
                        ruf.file=rf.id
                      )
                 JOIN reviewfilechanges AS rfc ON (
                        rfc.file=rf.id AND
                        rfc.uid=ruf.uid
                      )
                WHERE rf.review={review_id}
                  AND ruf.uid={author_id}
                  AND (rfc.state='performed' OR
                       rfc.to_reviewed!=ruf.reviewed)
                  AND rfc."""
            + condition,
            review_id=review_id,
            author_id=author_id,
            batch_id=self.id,
        ) as result:
            rows = await result.all()

        self.__reviewed_file_change_ids = set(
            filechange_id for filechange_id, to_reviewed in rows if to_reviewed
        )
        self.__unreviewed_file_change_ids = set(
            filechange_id for filechange_id, to_reviewed in rows if not to_reviewed
        )


@Batch.cached
async def fetch(
    critic: api.critic.Critic,
    batch_id: Optional[int],
    event: Optional[api.reviewevent.ReviewEvent],
) -> WrapperType:
    if batch_id is not None:
        condition = "id={batch_id}"
    else:
        condition = "event={event}"
    async with Batch.query(
        critic, [condition], batch_id=batch_id, event=event
    ) as result:
        return await Batch.makeOne(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    review: Optional[api.review.Review],
    author: Optional[api.user.User],
) -> List[WrapperType]:
    tables = [Batch.table()]
    conditions = ["TRUE"]
    if review or author:
        tables.append("reviewevents ON (reviewevents.id=batches.event)")
        if review:
            conditions.append("review={review}")
        if author:
            conditions.append("uid={author}")
    async with Batch.query(
        critic,
        f"""SELECT {Batch.columns()}
              FROM {" JOIN ".join(tables)}
             WHERE {" AND ".join(conditions)}""",
        review=review,
        author=author,
    ) as result:
        return await Batch.make(critic, result)


async def fetchUnpublished(
    review: api.review.Review, author: Optional[api.user.User]
) -> WrapperType:
    if author is None:
        author = review.critic.effective_user
    elif author != review.critic.effective_user:
        api.PermissionDenied.raiseUnlessSystem(review.critic)
    return Batch(review=review, author=author).wrap(review.critic)
