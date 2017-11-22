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

from .. import Transaction, Insert, LazyObject

from critic import api


class ReviewAssignmentsTransaction(LazyObject):
    def __init__(self, transaction: Transaction, review: api.review.Review):
        super().__init__()
        self.transaction = transaction
        self.review = review
        self.__created = False

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

    def __create(self) -> ReviewAssignmentsTransaction:
        if not self.__created:
            logger.debug("creating review assignments transaction in r/%d", self.review)
            self.transaction.items.append(
                Insert(
                    "reviewassignmentstransactions", returning="id", collector=self
                ).values(
                    review=self.review, assigner=self.transaction.critic.effective_user,
                )
            )
            self.__created = True
        return self

    @staticmethod
    def make(
        transaction: Transaction, review: api.review.Review
    ) -> ReviewAssignmentsTransaction:
        return transaction.shared.ensure(
            ReviewAssignmentsTransaction(transaction, review)
        ).__create()
