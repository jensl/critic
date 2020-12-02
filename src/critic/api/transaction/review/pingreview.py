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

logger = logging.getLogger(__name__)

from . import CreatedReviewPing, CreateReviewEvent
from ..base import TransactionBase

from critic import api


async def ping_review(
    transaction: TransactionBase, review: api.review.Review, message: str
) -> api.reviewping.ReviewPing:
    has_recipients = False

    open_issues = await review.open_issues
    for issue in open_issues:
        if (
            await issue.author in await review.owners
            or await issue.author in await review.assigned_reviewers
            or await issue.author in await review.active_reviewers
            or await issue.author in await review.watchers
        ):
            has_recipients = True
            break

    if not has_recipients:
        rfcs = await api.reviewablefilechange.fetchAll(review, is_reviewed=False)
        for rfc in rfcs:
            if await rfc.assigned_reviewers:
                has_recipients = True
                break

    if not has_recipients:
        raise api.review.Error("There are no (relevant) reviewers to ping!")

    return await CreatedReviewPing(transaction, review).insert(
        event=await CreateReviewEvent.ensure(transaction, review, "pinged"),
        message=message,
    )
