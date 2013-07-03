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

import sys

import dbutils
import gitutils
import reviewing.utils
import reviewing.filters

from textutils import json_encode, json_decode

db = None

def init():
    global db

    db = dbutils.Database()

def finish():
    global db

    if db:
        db.commit()
        db.close()
        db = None

def abort():
    global db

    if db:
        db.rollback()
        db.close()
        db = None

try:
    if len(sys.argv) > 1:
        init()

        for command in sys.argv[1:]:
            pending_mails = None

            if command == "generate-mails-for-batch":
                data = json_decode(sys.stdin.readline())
                batch_id = data["batch_id"]
                was_accepted = data["was_accepted"]
                is_accepted = data["is_accepted"]
                pending_mails = reviewing.utils.generateMailsForBatch(db, batch_id, was_accepted, is_accepted)
            elif command == "generate-mails-for-assignments-transaction":
                data = json_decode(sys.stdin.readline())
                transaction_id = data["transaction_id"]
                pending_mails = reviewing.utils.generateMailsForAssignmentsTransaction(db, transaction_id)
            elif command == "apply-filters":
                data = json_decode(sys.stdin.readline())
                filters = reviewing.filters.Filters()
                user = dbutils.User.fromId(db, data["user_id"]) if "user_id" in data else None
                if "review_id" in data:
                    review = dbutils.Review.fromId(db, data["review_id"], load_commits=False)
                    filters.setFiles(db, review=review)
                    filters.load(db, review=review, user=user,
                                 added_review_filters=data.get("added_review_filters", []),
                                 removed_review_filters=data.get("removed_review_filters", []))
                else:
                    repository = gitutils.Repository.fromId(db, data["repository_id"])
                    filters.setFiles(db, file_ids=data["file_ids"])
                    filters.load(db, repository=repository, recursive=data.get("recursive", False), user=user)
                sys.stdout.write(json_encode(filters.data) + "\n")
            else:
                print "unknown command: %s" % command
                sys.exit(1)

            if pending_mails is not None:
                sys.stdout.write(json_encode(pending_mails) + "\n")

        finish()
finally:
    abort()
