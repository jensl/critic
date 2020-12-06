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

import logging
from typing import Collection, Optional, Union, Callable, Coroutine, Any, cast

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from ..protocol import CreatedReviewEvent
from ..base import Finalizer, TransactionBase
from ..createapiobject import CreateAPIObject, APIObjectType


def raiseUnlessPublished(review: api.review.Review) -> None:
    if review.state == "draft":
        raise api.review.Error("Review has not been published")


class CreateReviewObject(CreateAPIObject[APIObjectType]):
    def __init__(
        self,
        transaction: TransactionBase,
        review: api.review.Review,
    ) -> None:
        super().__init__(transaction)
        self.review = review

    def scopes(self) -> Collection[str]:
        return (f"reviews/{int(self.review)}",)


class CreateReviewEvent(
    CreateReviewObject[api.reviewevent.ReviewEvent], api_module=api.reviewevent
):
    __created: Optional[api.reviewevent.ReviewEvent]

    def __init__(
        self,
        transaction: TransactionBase,
        review: api.review.Review,
        user: Optional[api.user.User],
        event_type: Optional[api.reviewevent.EventType],
    ):
        super().__init__(transaction, review)
        self.user = user
        self.type = event_type
        self.__created = None

    def __hash__(self) -> int:
        return hash((CreateReviewEvent, self.review))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CreateReviewEvent) and self.review == other.review

    async def create_payload(
        self, resource_name: str, subject: api.reviewevent.ReviewEvent, /
    ) -> CreatedReviewEvent:
        assert self.type is not None
        return CreatedReviewEvent(
            resource_name, subject.id, int(self.review), self.type
        )

    async def __create(self) -> api.reviewevent.ReviewEvent:
        assert self.type is not None
        if self.__created is None:
            self.__created = await self.insert(
                review=self.review, uid=self.user, type=self.type
            )
        return self.__created

    def check_compatibility(self, other: CreateReviewEvent) -> None:
        if other.type and self.type != other.type:
            raise api.TransactionError(
                f"Conflicting review event types in transaction: {self.type} != {other.type}"
            )
        if other.user and self.user != other.user:
            raise api.TransactionError(
                f"Conflicting review event users in transaction: {self.user} != {other.user}"
            )

    @staticmethod
    async def ensure(
        transaction: TransactionBase,
        review: api.review.Review,
        event_type: Optional[api.reviewevent.EventType] = None,
        *,
        user: Optional[api.user.User] = None,
    ) -> api.reviewevent.ReviewEvent:
        if event_type and user is None:
            user = transaction.critic.effective_user
        expected = CreateReviewEvent(transaction, review, user, event_type)
        actual = transaction.shared.ensure(expected)
        if actual.type is None:
            raise api.TransactionError("No review event in transaction!")
        actual.check_compatibility(expected)
        return await actual.__create()

    @staticmethod
    async def create(
        transaction: TransactionBase,
        review: api.review.Review,
        event_type: api.reviewevent.EventType,
        *,
        user: Optional[api.user.User] = None,
    ) -> api.reviewevent.ReviewEvent:
        if user is None:
            user = transaction.critic.effective_user
        return await CreateReviewEvent(transaction, review, user, event_type).__create()


class CreatedBatch(CreateReviewObject[api.batch.Batch], api_module=api.batch):
    pass


class CreateReviewFilter(
    CreateReviewObject[api.reviewfilter.ReviewFilter], api_module=api.reviewfilter
):
    pass


class CreatedReviewPing(
    CreateReviewObject[api.reviewping.ReviewPing], api_module=api.reviewping
):
    async def fetch(self, event_id: int, /) -> api.reviewping.ReviewPing:
        event = await api.reviewevent.fetch(self.critic, event_id)
        return await api.reviewping.fetch(self.critic, event)


class CreatedReviewIntegrationRequest(
    CreateReviewObject[api.reviewintegrationrequest.ReviewIntegrationRequest],
    api_module=api.reviewintegrationrequest,
):
    pass


class ReviewUser(Finalizer):
    tables = frozenset({"reviewusers"})

    def __init__(
        self, review: api.review.Review, user: api.user.User, is_owner: Optional[bool]
    ):
        self.review = review
        self.user = user
        self.is_owner = is_owner

    def __hash__(self) -> int:
        return hash((ReviewUser, self.review, self.user))

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        is_owner = add_user = False

        async with cursor.query(
            """SELECT owner
                 FROM reviewusers
                WHERE review={review_id}
                  AND uid={user_id}""",
            review_id=self.review.id,
            user_id=self.user.id,
        ) as result:
            try:
                is_owner = cast(bool, await result.scalar())
            except cursor.ZeroRowsInResult:
                add_user = True

        # We don't expect to be adding users just to set them as not owners.
        # Adding users as non-owners is naturally fine, but then |self.is_owner|
        # will be |None|, not |False|.
        assert not (add_user and self.is_owner is False)

        if add_user:
            await cursor.execute(
                """INSERT
                     INTO reviewusers (review, event, uid, owner)
                   VALUES ({review}, {event}, {user}, {owner})""",
                review=self.review,
                event=await CreateReviewEvent.ensure(transaction, self.review),
                user=self.user,
                owner=bool(self.is_owner),
            )
        elif self.is_owner is not None and is_owner != self.is_owner:
            await cursor.execute(
                """UPDATE reviewusers
                      SET owner={owner}
                    WHERE review={review_id}
                      AND uid={user_id}""",
                review_id=self.review,
                user_id=self.user,
                owner=self.is_owner,
            )

    @staticmethod
    def ensure(
        transaction: TransactionBase,
        review: api.review.Review,
        user: api.user.User,
        is_owner: Optional[bool] = None,
    ) -> None:
        transaction.finalizers.add(ReviewUser(review, user, is_owner))


class ReviewUserTag(Finalizer):
    tables = frozenset({"reviewusertags"})

    def __init__(
        self,
        review: api.review.Review,
        user: api.user.User,
        tag: str,
        value: Union[
            bool,
            Callable[
                [api.review.Review, api.user.User, dbaccess.BasicCursor],
                Coroutine[Any, Any, bool],
            ],
        ],
    ) -> None:
        self.review = review
        self.user = user
        self.tag = tag
        self.value = value

    def __hash__(self) -> int:
        return hash((ReviewUserTag, self.review, self.user, self.tag))

    def should_run_after(self, other: object) -> bool:
        return isinstance(other, ReviewUser)

    async def __call__(
        self, _: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        # This crashes (raises an exception that we don't catch) if the named
        # tag is not found in |reviewtags|.
        async with cursor.query(
            """SELECT id
                 FROM reviewtags
                WHERE name={tag}""",
            tag=self.tag,
        ) as result:
            tag_id = cast(int, await result.scalar())

        if isinstance(self.value, bool):
            value = self.value
        else:
            value = await self.value(self.review, self.user, cursor)

        if value:
            async with cursor.query(
                """SELECT 1
                     FROM reviewusertags
                    WHERE review={review_id}
                      AND uid={user_id}
                      AND tag={tag_id}""",
                review_id=self.review,
                user_id=self.user,
                tag_id=tag_id,
            ) as result:
                if not await result.empty():
                    return

            await cursor.execute(
                """INSERT
                     INTO reviewusertags (review, uid, tag)
                   VALUES ({review_id}, {user_id}, {tag_id})""",
                review_id=self.review,
                user_id=self.user,
                tag_id=tag_id,
            )
        else:
            # Execute this one "blindly". We don't care whether the tag was
            # there previously, only that it isn't there now.
            await cursor.execute(
                """DELETE
                     FROM reviewusertags
                    WHERE review={review_id}
                      AND uid={user_id}
                      AND tag={tag_id}""",
                review_id=self.review,
                user_id=self.user,
                tag_id=tag_id,
            )

    @staticmethod
    def ensure(
        transaction: TransactionBase,
        review: api.review.Review,
        user: api.user.User,
        tag: str,
        value: Union[
            bool,
            Callable[
                [api.review.Review, api.user.User, dbaccess.BasicCursor],
                Coroutine[Any, Any, bool],
            ],
        ] = True,
    ) -> None:
        transaction.finalizers.add(ReviewUserTag(review, user, tag, value))


async def has_unpublished_changes(
    review: api.review.Review, user: api.user.User, cursor: dbaccess.BasicCursor
) -> bool:
    unpublished = await api.batch.fetchUnpublished(review, user)
    return not await unpublished.is_empty


async def commits_behind_target_branch(
    repository: api.repository.Repository,
    head: api.commit.Commit,
    target_branch: api.branch.Branch,
    commits: api.commitset.CommitSet,
) -> int:
    upstreams = await commits.filtered_tails
    if len(upstreams) != 1:
        raise api.review.Error("Branch has multiple upstream commits")
    (upstream,) = upstreams
    if not await upstream.isAncestorOf(await target_branch.head):
        raise api.review.Error("Branch is not based on target branch")
    return await repository.low_level.revlist(
        include=[(await target_branch.head).sha1],
        exclude=[head.sha1],
        count=True,
    )
