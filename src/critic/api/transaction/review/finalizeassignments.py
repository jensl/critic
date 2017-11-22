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

from .reviewassignmentstransaction import ReviewAssignmentsTransaction
from .. import Transaction, Finalizer

from critic import api
from critic import dbaccess


class FinalizeAssignments(Finalizer):
    tables = frozenset({"reviewassignmentchanges", "reviewuserfiles", "reviewusertags"})

    def __init__(
        self, assignments_transaction: ReviewAssignmentsTransaction, user: api.user.User
    ) -> None:
        self.assignments_transaction = assignments_transaction
        self.review = assignments_transaction.review
        self.user = user

    def __hash__(self) -> int:
        return hash((FinalizeAssignments, self.review, self.user))

    async def __call__(
        self, _: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        from ....reviewing.assignments import calculateAssignments, currentAssignments

        transaction_id = int(self.assignments_transaction)

        expected_assignments = await calculateAssignments(
            self.review, subject=self.user
        )
        actual_assignments = await currentAssignments(self.review, subject=self.user)

        missing_assignments = expected_assignments - actual_assignments
        obsolete_assignments = actual_assignments - expected_assignments

        if not (missing_assignments or obsolete_assignments):
            return

        logger.debug("finalizing assignments for %r in r/%d", self.user, self.review)

        if missing_assignments:
            logger.debug("  missing assignments: %r", missing_assignments)

            await cursor.executemany(
                """INSERT
                     INTO reviewassignmentchanges
                            (transaction, file, uid, assigned)
                   SELECT {transaction}, id, {user}, TRUE
                     FROM reviewfiles
                    WHERE review={review}
                      AND changeset={changeset}
                      AND file={file}""",
                [
                    dict(
                        transaction=transaction_id,
                        user=self.user.id,
                        review=self.review.id,
                        changeset=assignment.changeset.id,
                        file=assignment.file.id,
                    )
                    for assignment in missing_assignments
                ],
            )

            await cursor.executemany(
                """INSERT
                     INTO reviewuserfiles (file, uid)
                   SELECT id, {user}
                     FROM reviewfiles
                    WHERE review={review}
                      AND changeset={changeset}
                      AND file={file}""",
                [
                    dict(
                        user=self.user.id,
                        review=self.review.id,
                        changeset=assignment.changeset.id,
                        file=assignment.file.id,
                    )
                    for assignment in missing_assignments
                ],
            )

        if obsolete_assignments:
            logger.debug("  obsolete assignments: %r", obsolete_assignments)

            await cursor.executemany(
                """INSERT
                     INTO reviewassignmentchanges
                            (transaction, file, uid, assigned)
                   SELECT {transaction}, id, {user}, FALSE
                     FROM reviewfiles
                    WHERE review={review}
                      AND changeset={changeset}
                      AND file={file}""",
                [
                    dict(
                        transaction=transaction_id,
                        user=self.user.id,
                        review=self.review.id,
                        changeset=assignment.changeset.id,
                        file=assignment.file.id,
                    )
                    for assignment in obsolete_assignments
                ],
            )

            await cursor.executemany(
                """DELETE
                     FROM reviewuserfiles
                    WHERE uid={user}
                      AND file IN (
                     SELECT id
                       FROM reviewfiles
                      WHERE review={review}
                        AND changeset={changeset}
                        AND file={file}
                    )""",
                [
                    dict(
                        user=self.user.id,
                        review=self.review.id,
                        changeset=assignment.changeset.id,
                        file=assignment.file.id,
                    )
                    for assignment in obsolete_assignments
                ],
            )
