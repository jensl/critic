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
from typing import Dict

from critic.api.transaction.review.submitchanges import submit_changes

logger = logging.getLogger(__name__)

from ..base import TransactionBase, Finalizer
from ..modifier import Modifier

from critic import api
from critic import dbaccess


class UpdateWouldBeAcceptedTag(Finalizer):
    tables = frozenset(("reviewusertags",))

    def __init__(self, modifier: Modifier[api.review.Review]):
        self.__modifier = modifier

    @property
    def review(self) -> api.review.Review:
        return self.__modifier.subject

    def __hash__(self) -> int:
        return hash((UpdateWouldBeAcceptedTag, self.review))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, UpdateWouldBeAcceptedTag) and self.review == other.review
        )

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        review = self.review
        would_be_accepted: Dict[api.user.User, bool] = {}
        for user in await review.users:
            batch = await (await api.batch.fetchUnpublished(review, user)).reload()
            if await batch.is_empty:
                continue
            logger.debug("%r: faux-submitting changes for %r", review, user)
            async with transaction.savepoint(
                "update_would_be_accepted_tag"
            ) as savepoint:
                await submit_changes(transaction, review, batch, None)
                await savepoint.run_finalizers()
                would_be_accepted[user] = await (
                    await self.__modifier.reload()
                ).is_accepted
        async with dbaccess.Query[int](
            cursor,
            """
            SELECT id
              FROM reviewtags
             WHERE name='would_be_accepted'
            """,
        ) as result:
            tag_id = await result.scalar()
        await cursor.delete(
            "reviewusertags",
            review=review,
            tag=tag_id,
        )
        users = [user for user, has_tag in would_be_accepted.items() if has_tag]
        logger.debug("%r would be accepted by %r", review, users)
        if users:
            await cursor.insertmany(
                "reviewusertags",
                (
                    dbaccess.parameters(review=review, uid=user, tag=tag_id)
                    for user in users
                ),
            )
