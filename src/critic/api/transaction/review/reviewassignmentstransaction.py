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
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api
from ..base import TransactionBase
from ..insertandcollect import InsertAndCollect
from . import CreateReviewEvent


class ReviewAssignmentsTransaction:
    __created: Optional[int]

    def __init__(self, transaction: TransactionBase, review: api.review.Review):
        super().__init__()
        self.transaction = transaction
        self.review = review
        self.__created = None

    def __hash__(self) -> int:
        return hash((ReviewAssignmentsTransaction, self.review))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ReviewAssignmentsTransaction)
            and self.review == other.review
        )

    def __repr__(self) -> str:
        return "ReviewAssignmentsTransaction(r/%d, %s)" % (
            self.review,
            "old" if self.__created else "new",
        )

    def __adapt__(self) -> int:
        return self.id

    @property
    def id(self) -> int:
        assert self.__created is not None
        return self.__created

    async def __create(self) -> ReviewAssignmentsTransaction:
        if self.__created is None:
            logger.debug("creating review assignments transaction in r/%d", self.review)
            self.__created = await self.transaction.execute(
                InsertAndCollect[int, int](
                    "reviewassignmentstransactions", returning="id"
                ).values(
                    review=self.review,
                    event=await CreateReviewEvent.ensure(
                        self.transaction, self.review, "assignments"
                    ),
                    assigner=self.transaction.critic.effective_user,
                )
            )
        return self

    @staticmethod
    async def make(
        transaction: TransactionBase, review: api.review.Review
    ) -> ReviewAssignmentsTransaction:
        return await transaction.shared.ensure(
            ReviewAssignmentsTransaction(transaction, review)
        ).__create()
