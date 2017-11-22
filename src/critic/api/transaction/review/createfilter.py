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
from typing import Collection

logger = logging.getLogger(__name__)

from . import CreatedReviewFilter, ReviewUser
from .. import Transaction, Insert, InsertMany
from .finalizeassignments import FinalizeAssignments
from .reviewassignmentstransaction import ReviewAssignmentsTransaction
from .updatereviewtags import UpdateReviewTags

from critic import api


def create_filter(
    transaction: Transaction,
    review: api.review.Review,
    subject: api.user.User,
    filter_type: api.reviewfilter.FilterType,
    path: str,
    default_scope: bool,
    scopes: Collection[api.reviewscope.ReviewScope],
) -> CreatedReviewFilter:
    reviewfilter = CreatedReviewFilter(transaction, review)

    transaction.tables.add("reviewfilters")
    transaction.items.append(
        Insert("reviewfilters", returning="id", collector=reviewfilter).values(
            review=review,
            uid=subject,
            type=filter_type,
            path=path,
            default_scope=default_scope,
            creator=transaction.critic.effective_user,
        )
    )

    if scopes:
        transaction.items.append(
            InsertMany(
                "reviewfilterscopes",
                ["filter", "scope"],
                (dict(filter=reviewfilter, scope=scope) for scope in scopes),
            )
        )

    assignments_transaction = ReviewAssignmentsTransaction.make(transaction, review)

    transaction.tables.add("reviewfilterchanges")
    transaction.items.append(
        Insert("reviewfilterchanges").values(
            transaction=assignments_transaction,
            uid=subject,
            type=filter_type,
            path=path,
            created=True,
        )
    )

    ReviewUser.ensure(transaction, review, subject)

    transaction.finalizers.add(FinalizeAssignments(assignments_transaction, subject))
    transaction.finalizers.add(UpdateReviewTags(review))

    return reviewfilter
