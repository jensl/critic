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
from typing import Tuple, Optional, Union, Callable, Coroutine, Any, cast

logger = logging.getLogger(__name__)

from .. import Transaction, Finalizer, Insert, LazyAPIObject, protocol
from critic import api
from critic import dbaccess


class CreatedReview(LazyAPIObject, api_module=api.review):
    state = "draft"

    def __init__(
        self,
        transaction: Transaction,
        branch: Optional[Union[api.branch.Branch, CreatedBranch]],
        commits: api.commitset.CommitSet,
    ) -> None:
        super().__init__(transaction)
        self.__branch = branch
        self.__commits = commits

    @property
    async def branch(self) -> Optional[Union[api.branch.Branch, CreatedBranch]]:
        return self.__branch

    @property
    async def commits(self) -> api.commitset.CommitSet:
        return self.__commits

    @property
    async def initial_commits_pending(self) -> bool:
        return True


class CreatedReviewObject(LazyAPIObject):
    def __init__(
        self, transaction: Transaction, review: Union[api.review.Review, CreatedReview]
    ) -> None:
        super().__init__(transaction)
        self.review = review

    def scopes(self) -> LazyAPIObject.Scopes:
        return (f"reviews/{int(self.review)}",)


class CreatedReviewEvent(CreatedReviewObject, api_module=api.reviewevent):
    def __init__(
        self,
        transaction: Transaction,
        review: Union[api.review.Review, CreatedReview],
        user: api.user.User,
        event_type: api.reviewevent.EventType,
    ):
        super().__init__(transaction, review)
        self.user = user
        self.type = event_type
        self.__created = False

    def __hash__(self) -> int:
        return hash((CreatedReviewEvent, self.review, self.user.id, self.type))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, CreatedReviewEvent)
            and self.review == other.review
            and self.user == other.user
            and self.type == other.type
        )

    async def create_payload(
        self, resource_name: str, subject: api.review.Review, /
    ) -> protocol.CreatedReviewEvent:
        return protocol.CreatedReviewEvent(
            resource_name, subject.id, int(self.review), self.type
        )

    def __create(self) -> Optional[CreatedReviewEvent]:
        if self.__created:
            return None
        self.insert(review=self.review, uid=self.user, type=self.type)
        self.__created = True
        return self

    @staticmethod
    def ensure(
        transaction: Transaction,
        review: Union[api.review.Review, CreatedReview],
        event_type: api.reviewevent.EventType,
        *,
        user: api.user.User = None,
    ) -> Optional[CreatedReviewEvent]:
        if user is None:
            user = transaction.critic.effective_user
        return transaction.shared.ensure(
            CreatedReviewEvent(transaction, review, user, event_type)
        ).__create()


class CreatedBatch(CreatedReviewObject, api_module=api.batch):
    pass


class CreatedReviewFilter(CreatedReviewObject, api_module=api.reviewfilter):
    pass


class CreatedReviewPing(CreatedReviewObject, api_module=api.reviewping):
    @staticmethod
    async def fetch(
        critic: api.critic.Critic, event_id: int
    ) -> api.reviewping.ReviewPing:
        event = await api.reviewevent.fetch(critic, event_id)
        return await api.reviewping.fetch(critic, event)


class CreatedReviewIntegrationRequest(
    CreatedReviewObject, api_module=api.reviewintegrationrequest
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
        self, _: Transaction, cursor: dbaccess.TransactionCursor
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
                     INTO reviewusers (review, uid, owner)
                   VALUES ({review_id}, {user_id}, {owner})""",
                review_id=self.review,
                user_id=self.user,
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
        transaction: Transaction,
        review: api.review.Review,
        user: api.user.User,
        is_owner: bool = None,
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
        self, _: Transaction, cursor: dbaccess.TransactionCursor
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
        transaction: Transaction,
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


from .create import create_review
from .modify import ModifyReview
from ..branch import CreatedBranch

__all__ = ["create_review", "ModifyReview"]
