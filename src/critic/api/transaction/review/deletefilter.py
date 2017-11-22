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

from .. import Transaction, Insert, Delete
from .finalizeassignments import FinalizeAssignments
from .reviewassignmentstransaction import ReviewAssignmentsTransaction
from .updatereviewtags import UpdateReviewTags

from critic import api


async def delete_filter(
    transaction: Transaction,
    review: api.review.Review,
    filter: api.reviewfilter.ReviewFilter,
) -> None:
    transaction.items.append(Delete(filter))

    assignments_transaction = ReviewAssignmentsTransaction.make(transaction, review)

    subject = await filter.subject

    transaction.items.append(
        Insert("reviewfilterchanges").values(
            transaction=assignments_transaction,
            uid=subject,
            type=filter.type,
            path=filter.path,
            created=False,
        )
    )

    transaction.finalizers.add(FinalizeAssignments(assignments_transaction, subject))
    transaction.finalizers.add(UpdateReviewTags(review))
