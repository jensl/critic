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

from operation import Operation, OperationResult

class AddRecipientFilter(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "user_id": int,
                                   "include": bool })

    def process(self, db, user, review_id, user_id, include):
        cursor = db.cursor()
        cursor.execute("SELECT include FROM reviewrecipientfilters WHERE review=%s AND uid=%s", (review_id, user_id))
        row = cursor.fetchone()

        if row:
            if row[0] != include:
                cursor.execute("UPDATE reviewrecipientfilters SET include=%s WHERE review=%s AND uid=%s", (include, review_id, user_id))
                db.commit()
        else:
            cursor.execute("INSERT INTO reviewrecipientfilters (review, uid, include) VALUES (%s, %s, %s)", (review_id, user_id, include))
            db.commit()

        return OperationResult()
