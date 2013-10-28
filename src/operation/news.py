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

class AddNewsItem(Operation):
    """Add news item."""

    def __init__(self):
        Operation.__init__(self, { "text": str })

    def process(self, db, user, text):
        Operation.requireRole(db, "newswriter", user)

        cursor = db.cursor()
        cursor.execute("INSERT INTO newsitems (text) VALUES (%s) RETURNING id", (text,))
        item_id = cursor.fetchone()[0]
        db.commit()

        return OperationResult(item_id=item_id)

class EditNewsItem(Operation):
    """Add news item."""

    def __init__(self):
        Operation.__init__(self, { "item_id": int,
                                   "text": str })

    def process(self, db, user, item_id, text):
        Operation.requireRole(db, "newswriter", user)

        db.cursor().execute("UPDATE newsitems SET text=%s WHERE id=%s", (text, item_id))
        db.commit()

        return OperationResult()
