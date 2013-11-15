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

from operation import Operation, OperationResult

class MarkFiles(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "reviewed": bool,
                                   "changeset_ids": [int],
                                   "file_ids": [int] })

    def process(req, db, user, review_id, reviewed, changeset_ids, file_ids):
        review = dbutils.Review.fromId(db, review_id)

        cursor = db.cursor()

        # Revert any draft changes the user has for the specified files in
        # the specified changesets.
        cursor.execute("""DELETE FROM reviewfilechanges
                                USING reviewfiles
                                WHERE reviewfilechanges.uid=%s
                                  AND reviewfilechanges.state='draft'
                                  AND reviewfilechanges.file=reviewfiles.id
                                  AND reviewfiles.review=%s
                                  AND reviewfiles.changeset=ANY (%s)
                                  AND reviewfiles.file=ANY (%s)""",
                       (user.id, review.id, changeset_ids, file_ids))

        if reviewed:
            from_state, to_state = 'pending', 'reviewed'
        else:
            from_state, to_state = 'reviewed', 'pending'

        # Insert draft changes for every file whose state would be updated.
        cursor.execute("""INSERT INTO reviewfilechanges (file, uid, from_state, to_state)
                               SELECT reviewfiles.id, reviewuserfiles.uid, reviewfiles.state, %s
                                 FROM reviewfiles
                                 JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id AND reviewuserfiles.uid=%s)
                                WHERE reviewfiles.review=%s
                                  AND reviewfiles.state=%s
                                  AND reviewfiles.changeset=ANY (%s)
                                  AND reviewfiles.file=ANY (%s)""",
                       (to_state, user.id, review.id, from_state, changeset_ids, file_ids))

        db.commit()

        return OperationResult(draft_status=review.getDraftStatus(db, user))
