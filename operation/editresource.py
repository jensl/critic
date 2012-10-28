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

from operation import Operation, OperationResult, OperationError, Optional

class StoreResource(Operation):
    """Store new revision of user-edited resource."""

    def __init__(self):
        Operation.__init__(self, { "name": str,
                                   "source": str })

    def process(self, db, user, name, source):
        cursor = db.cursor()
        cursor.execute("SELECT MAX(revision) FROM userresources WHERE uid=%s AND name=%s", (user.id, name))

        current_revision = cursor.fetchone()[0] or 0
        next_revision = current_revision + 1

        cursor.execute("INSERT INTO userresources (uid, name, revision, source) VALUES (%s, %s, %s, %s)", (user.id, name, next_revision, source))

        db.commit()

        return OperationResult()

class ResetResource(Operation):
    """Reset user-edited resource back to its original."""

    def __init__(self):
        Operation.__init__(self, { "name": str })

    def process(self, db, user, name):
        cursor = db.cursor()
        cursor.execute("SELECT MAX(revision) FROM userresources WHERE uid=%s AND name=%s", (user.id, name))

        current_revision = cursor.fetchone()[0] or 0

        if current_revision > 0:
            cursor.execute("SELECT source FROM userresources WHERE uid=%s AND name=%s AND revision=%s", (user.id, name, current_revision))

            if cursor.fetchone()[0] is not None:
                next_revision = current_revision + 1

                cursor.execute("INSERT INTO userresources (uid, name, revision) VALUES (%s, %s, %s)", (user.id, name, next_revision))

                db.commit()

        return OperationResult()

class RestoreResource(Operation):
    """Restore last user-edited revision of resource after it's been reset."""

    def __init__(self):
        Operation.__init__(self, { "name": str })

    def process(self, db, user, name):
        cursor = db.cursor()
        cursor.execute("SELECT MAX(revision) FROM userresources WHERE uid=%s AND name=%s", (user.id, name))

        current_revision = cursor.fetchone()[0] or 0

        if current_revision > 1:
            cursor.execute("SELECT source FROM userresources WHERE uid=%s AND name=%s AND revision=%s", (user.id, name, current_revision))

            if cursor.fetchone()[0] is None:
                cursor.execute("DELETE FROM userresources WHERE uid=%s AND name=%s AND revision=%s", (user.id, name, current_revision))

                db.commit()

        return OperationResult()
