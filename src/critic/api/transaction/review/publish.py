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
from typing import Union

logger = logging.getLogger(__name__)

from . import CreatedReview, CreatedReviewEvent
from .. import Transaction, Query, Update

from critic import api


def publish(
    transaction: Transaction, review: Union[api.review.Review, CreatedReview]
) -> None:
    def checkReview(summary: str, branch: int) -> None:
        if not summary:
            raise api.review.Error("Review summary not set")
        if not branch:
            raise api.review.Error("Review branch not set")

    transaction.items.append(
        Query(
            """SELECT summary, branch
                 FROM reviews
                WHERE id={review}""",
            review=review,
            collector=checkReview,
        )
    )

    transaction.items.append(Update(review).set(state="open"))

    CreatedReviewEvent.ensure(transaction, review, "published")
