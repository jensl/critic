# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import re

import dbutils
import gitutils
import configuration

from operation import (Operation, OperationResult, OperationFailure, Review,
                       Repository, SHA1)

class CheckSerial(Operation):
    def __init__(self):
        super(CheckSerial, self).__init__({ "review_id": int,
                                            "serial": int })

    def process(self, db, user, review_id, serial):
        cursor = db.readonly_cursor()
        cursor.execute("SELECT serial FROM reviews WHERE id=%s", (review_id,))

        current_serial, = cursor.fetchone()

        if serial == current_serial:
            interval = user.getPreference(db, "review.updateCheckInterval")
            return OperationResult(stale=False, interval=interval)

        return OperationResult(stale=True)

class RebaseBranch(Operation):
    def __init__(self):
        super(RebaseBranch, self).__init__({ "repository": Repository,
                                             "branch_name": str,
                                             "base_branch_name": str })

    def process(self, db, user, repository, branch_name, base_branch_name):
        branch = dbutils.Branch.fromName(db, repository, branch_name)
        base_branch = dbutils.Branch.fromName(db, repository, base_branch_name)

        branch.rebase(db, base_branch)

        db.commit()

        return OperationResult()

class SuggestReview(Operation):
    def __init__(self):
        super(SuggestReview, self).__init__({ "repository": Repository,
                                              "sha1": SHA1 })

    def process(self, db, user, repository, sha1):
        try:
            commit = gitutils.Commit.fromSHA1(db, repository, sha1)
        except gitutils.GitReferenceError:
            raise OperationFailure(
                code="invalidsha1",
                title="Invalid SHA-1",
                message="No such commit: %s in %s" % (sha1, repository.path))

        suggestions = {}

        cursor = db.readonly_cursor()
        cursor.execute("""SELECT reviews.id
                            FROM reviews
                           WHERE reviews.summary=%s""",
                       (commit.summary(),))
        for review_id, in cursor:
            review = dbutils.Review.fromId(db, review_id)
            if review.state != 'dropped':
                suggestions[review_id] = review.getReviewState(db)

        return OperationResult(summary=commit.summary(), reviews=reviews)
