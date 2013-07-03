# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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
import reviewing.utils

from operation import Operation, OperationResult

class QueryGlobalFilters(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        reviewers, watchers = reviewing.utils.queryFilters(db, user, review, globalfilters=True)
        return OperationResult(reviewers=[dbutils.User.fromId(db, user_id).getJSON() for user_id in reviewers],
                               watchers=[dbutils.User.fromId(db, user_id).getJSON() for user_id in watchers])

class ApplyGlobalFilters(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        reviewing.utils.applyFilters(db, user, review, globalfilters=True)
        return OperationResult()

class QueryParentFilters(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        reviewers, watchers = reviewing.utils.queryFilters(db, user, review, parentfilters=True)
        return OperationResult(reviewers=[dbutils.User.fromId(db, user_id).getJSON() for user_id in reviewers],
                               watchers=[dbutils.User.fromId(db, user_id).getJSON() for user_id in watchers])

class ApplyParentFilters(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        reviewing.utils.applyFilters(db, user, review, parentfilters=True)
        return OperationResult()
