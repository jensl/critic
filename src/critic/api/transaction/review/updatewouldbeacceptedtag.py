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

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from ..base import TransactionBase, Finalizer
from .submitchanges import submit_changes


class UpdateWouldBeAcceptedTag(Finalizer):
    tables = frozenset(("reviewusertags",))

    def __init__(self, review: api.review.Review):
        self.__review = review
        super().__init__(self.__review)

    async def is_accepted(self) -> bool:
        return await (await self.__review.refresh()).is_accepted

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        is_accepted_now = await self.is_accepted()
        logger.debug(f"{is_accepted_now=}")
        accepted_after_publish: Dict[api.user.User, bool] = {}
        for user in await self.__review.users:
            batch = await api.batch.fetchUnpublished(self.__review, user)
            if await batch.is_empty:
                continue
            logger.debug("%r: faux-submitting changes for %r", self.__review, user)
            async with transaction.savepoint(
                "update_would_be_accepted_tag"
            ) as savepoint:
                await submit_changes(transaction, self.__review, batch, None)
                await savepoint.run_finalizers()
                is_accepted_then = await self.is_accepted()
                logger.debug(f"{user=} {is_accepted_then=}")
                if is_accepted_then != is_accepted_now:
                    accepted_after_publish[user] = is_accepted_then
        logger.debug(f"{accepted_after_publish=}")
        would_be_accepted = await api.reviewtag.fetch(
            transaction.critic, name="would_be_accepted"
        )
        would_be_unaccepted = await api.reviewtag.fetch(
            transaction.critic, name="would_be_unaccepted"
        )
        await cursor.delete(
            "reviewusertags",
            review=self.__review,
            tag=[would_be_accepted, would_be_unaccepted],
        )
        should_have_would_be_accepted = [
            user for user, is_accepted in accepted_after_publish.items() if is_accepted
        ]
        should_have_would_be_unaccepted = [
            user
            for user, is_accepted in accepted_after_publish.items()
            if not is_accepted
        ]
        if should_have_would_be_accepted:
            logger.debug(
                "%r would be accepted by %r",
                self.__review,
                should_have_would_be_accepted,
            )
            await cursor.insertmany(
                "reviewusertags",
                (
                    dbaccess.parameters(
                        review=self.__review,
                        uid=user,
                        tag=would_be_accepted,
                    )
                    for user in should_have_would_be_accepted
                ),
            )
        if should_have_would_be_unaccepted:
            logger.debug(
                "%r would be unaccepted by %r",
                self.__review,
                should_have_would_be_unaccepted,
            )
            await cursor.insertmany(
                "reviewusertags",
                (
                    dbaccess.parameters(
                        review=self.__review,
                        uid=user,
                        tag=would_be_unaccepted,
                    )
                    for user in should_have_would_be_unaccepted
                ),
            )
