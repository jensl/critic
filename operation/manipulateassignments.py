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

import itertools

import dbutils
import mailutils
import review.utils

from operation import Operation, OperationResult

class GetAssignedChanges(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "user_name": str })

    def process(self, db, user, review_id, user_name):
        reviewer = dbutils.User.fromName(db, user_name)

        cursor = db.cursor()
        cursor.execute("SELECT file FROM fullreviewuserfiles WHERE review=%s AND assignee=%s", (review_id, reviewer.id))

        return OperationResult(files=[file_id for (file_id,) in cursor])

class SetAssignedChanges(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "user_name": str,
                                   "files": [int] })

    def process(self, db, user, review_id, user_name, files):
        reviewer = dbutils.User.fromName(db, user_name)
        new_file_ids = set(files)

        cursor = db.cursor()
        cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (review_id, reviewer.id))

        if not cursor.fetchone():
            cursor.execute("INSERT INTO reviewusers (review, uid) VALUES (%s, %s)", (review_id, reviewer.id))
            current_file_ids = set()
        else:
            cursor.execute("SELECT file FROM fullreviewuserfiles WHERE review=%s AND assignee=%s", (review_id, reviewer.id))
            current_file_ids = set(file_id for (file_id,) in cursor)

        delete_file_ids = current_file_ids - new_file_ids
        new_file_ids -= current_file_ids

        if delete_file_ids or new_file_ids:
            cursor.execute("INSERT INTO reviewassignmentstransactions (review, assigner) VALUES (%s, %s) RETURNING id", (review_id, user.id))
            transaction_id = cursor.fetchone()[0]

        if delete_file_ids:
            cursor.executemany("""INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned)
                                       SELECT %s, reviewfiles.id, reviewuserfiles.uid, false
                                         FROM reviewfiles
                                         JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id)
                                        WHERE reviewfiles.review=%s
                                          AND reviewfiles.file=%s
                                          AND reviewuserfiles.uid=%s""",
                               itertools.izip(itertools.repeat(transaction_id),
                                              itertools.repeat(review_id),
                                              delete_file_ids,
                                              itertools.repeat(reviewer.id)))

            cursor.executemany("""DELETE FROM reviewuserfiles
                                        USING reviewfiles
                                        WHERE reviewuserfiles.file=reviewfiles.id
                                          AND reviewfiles.review=%s
                                          AND reviewfiles.file=%s
                                          AND reviewuserfiles.uid=%s""",
                               itertools.izip(itertools.repeat(review_id),
                                              delete_file_ids,
                                              itertools.repeat(reviewer.id)))

        if new_file_ids:
            cursor.executemany("""INSERT INTO reviewuserfiles (file, uid)
                                       SELECT reviewfiles.id, %s
                                         FROM reviewfiles
                                        WHERE reviewfiles.review=%s
                                          AND reviewfiles.file=%s""",
                               itertools.izip(itertools.repeat(reviewer.id),
                                              itertools.repeat(review_id),
                                              new_file_ids))

            cursor.executemany("""INSERT INTO reviewassignmentchanges (transaction, file, uid, assigned)
                                       SELECT %s, reviewfiles.id, %s, true
                                         FROM reviewfiles
                                        WHERE reviewfiles.review=%s
                                          AND reviewfiles.file=%s""",
                               itertools.izip(itertools.repeat(transaction_id),
                                              itertools.repeat(reviewer.id),
                                              itertools.repeat(review_id),
                                              new_file_ids))

        if delete_file_ids or new_file_ids:
            cursor.execute("UPDATE reviews SET serial=serial+1 WHERE id=%s", (review_id,))

            pending_mails = review.utils.generateMailsForAssignmentsTransaction(db, transaction_id)

            db.commit()

            mailutils.sendPendingMails(pending_mails)

        return OperationResult()
