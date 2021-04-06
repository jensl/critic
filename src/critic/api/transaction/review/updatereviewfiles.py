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
from typing import Collection, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from ..base import TransactionBase


async def update_review_files(
    review: api.review.Review, cursor: dbaccess.TransactionCursor
) -> None:
    async with dbaccess.Query[Tuple[int, bool, bool]](
        cursor,
        """
        SELECT rf.id, rf.reviewed,
                      COUNT(ruf.reviewed)
                 FROM reviewfiles AS rf
      LEFT OUTER JOIN reviewuserfiles AS ruf ON (
                        rf.id=ruf.file AND
                        ruf.reviewed
                      )
                WHERE rf.review={review}
             GROUP BY rf.id, rf.reviewed
             """,
        review=review,
    ) as result1:
        state = await result1.all()

    logger.debug(f"{state=}")

    async with dbaccess.Query[Tuple[int, bool]](
        cursor,
        """SELECT id, correct_value
             FROM (
               SELECT rf.id, rf.reviewed AS current_value,
                      COUNT(ruf.reviewed)!=0 AS correct_value
                 FROM reviewfiles AS rf
      LEFT OUTER JOIN reviewuserfiles AS ruf ON (
                        rf.id=ruf.file AND
                        ruf.reviewed
                      )
                WHERE rf.review={review}
             GROUP BY rf.id, rf.reviewed
             ) AS adjustments_needed
            WHERE current_value!=correct_value""",
        review=review,
    ) as result:
        adjustments_needed = await result.all()

    logger.debug(f"{adjustments_needed=}")

    change_to_reviewed = []
    change_to_pending = []

    for file_id, should_be_reviewed in adjustments_needed:
        if should_be_reviewed:
            change_to_reviewed.append(file_id)
        else:
            change_to_pending.append(file_id)

    await cursor.execute(
        """UPDATE reviewfiles
              SET reviewed=TRUE
            WHERE review={review}
              AND id=ANY({files})""",
        review=review,
        files=change_to_reviewed,
    )
    await cursor.execute(
        """UPDATE reviewfiles
              SET reviewed=FALSE
            WHERE review={review}
              AND id=ANY({files})""",
        review=review,
        files=change_to_pending,
    )


class UpdateReviewFiles:
    tables = frozenset({"reviewfiles"})

    def __init__(self, review: api.review.Review) -> None:
        self.__review = review

    @property
    def table_names(self) -> Collection[str]:
        return ("reviewfiles",)

    async def __call__(
        self, transaction: TransactionBase, cursor: dbaccess.TransactionCursor
    ) -> None:
        await update_review_files(self.__review, cursor)
