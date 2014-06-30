# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import dbutils

from operation import Operation, OperationResult, OperationFailure, Review

# This operation has no UI entry point; it is used during testing.
class ArchiveBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review })

    def process(self, db, user, review):
        if review.branch.archived:
            raise OperationFailure(
                code="invalidstate",
                title="Branch already archived!",
                message="The review's branch has already been archived.")

        if review.state not in ("closed", "dropped"):
            raise OperationFailure(
                code="invalidstate",
                title="Invalid review state!",
                message=("The review must be closed or dropped to archive "
                         "its branch."))

        review.branch.archive(db)
        review.cancelScheduledBranchArchival(db)

        db.commit()

        return OperationResult()

class ResurrectBranch(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review })

    def process(self, db, user, review):
        if not review.branch.archived:
            raise OperationFailure(
                code="invalidstate",
                title="Branch not archived!",
                message="The review's branch has not been archived.")

        review.branch.resurrect(db)
        delay = review.scheduleBranchArchival(db)

        db.commit()

        return OperationResult(delay=delay)

# This operation has no UI entry point; it is used during testing.
class ScheduleBranchArchival(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review,
                                   "delay": int })

    def process(self, db, user, review, delay):
        # This operation intentionally doesn't check that the review is closed
        # or dropped, or that the branch isn't already archived.  Those checks
        # are performed by dbutils.Review.scheduleBranchArchival(), which is a
        # no-op if the conditions aren't met.

        review.scheduleBranchArchival(db, delay=delay)

        db.commit()

        return OperationResult()
