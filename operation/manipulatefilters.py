# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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
import gitutils
import mailutils

import review.utils as review_utils

from operation import Operation, OperationResult, OperationError, Optional

class AddReviewFilters(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "filters": [{ "type": set(["reviewer", "watcher"]),
                                                 "user_names": Optional([str]),
                                                 "user_ids": Optional([int]),
                                                 "paths": Optional([str]),
                                                 "directory_ids": Optional([int]),
                                                 "file_ids": Optional([int]) }] })

    def process(self, db, creator, review_id, filters):
        review = dbutils.Review.fromId(db, review_id)
        by_user = {}

        for filter in filters:
            if "user_ids" in filter:
                user_ids = set(filter["user_ids"])
            else:
                user_ids = set([])

            if "user_names" in filter:
                for user_name in filter["user_names"]:
                    user_ids.add(dbutils.User.fromName(db, user_name).id)

            if "directory_ids" in filter:
                directory_ids = set(filter["directory_ids"])
            else:
                directory_ids = set([])

            if "file_ids" in filter:
                file_ids = set(filter["file_ids"])
            else:
                file_ids = set([])

            if "paths" in filter:
                for path in filter["paths"]:
                    if not path or path == "/":
                        directory_ids.add(0)
                    elif path.endswith("/") or dbutils.is_directory(db, path) or ("." not in path.split("/")[-1] and not dbutils.is_file(db, path)):
                        directory_ids.add(dbutils.find_directory(db, path))
                    else:
                        file_ids.add(dbutils.find_file(db, path))

            for user_id in user_ids:
                reviewer_directory_ids, reviewer_file_ids, watcher_directory_ids, watcher_file_ids = by_user.setdefault(user_id, (set(), set(), set(), set()))

                if filter["type"] == "reviewer":
                    reviewer_directory_ids |= directory_ids
                    reviewer_file_ids |= file_ids
                else:
                    watcher_directory_ids |= directory_ids
                    watcher_file_ids |= file_ids

        pending_mails = []

        for user_id, args in by_user.items():
            user = dbutils.User.fromId(db, user_id)
            pending_mails.extend(review_utils.addReviewFilters(db, creator, user, review, *args))

        db.commit()

        mailutils.sendPendingMails(pending_mails)

        return OperationResult()

class RemoveReviewFilter(Operation):
    def __init__(self):
        Operation.__init__(self, { "filter_id": int })

    def process(self, db, user, filter_id):
        cursor = db.cursor()
        cursor.execute("DELETE FROM reviewfilters WHERE id=%s", (filter_id,))

        db.commit()

        return OperationResult()
