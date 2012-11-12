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

from operation import Operation, OperationResult, OperationError, OperationFailure, Optional

class SetFullname(Operation):
    def __init__(self):
        Operation.__init__(self, { "user_id": int,
                                   "value": str })

    def process(self, db, user, user_id, value):
        if user.id != user_id and not user.hasRole(db, "administrator"):
            raise OperationFailure(code="notallowed",
                                   title="Not allowed!",
                                   message="Operation not permitted.")

        if not value.strip():
            raise OperationError("empty display name is not allowed")

        db.cursor().execute("UPDATE users SET fullname=%s WHERE id=%s", (value.strip(), user_id))
        db.commit()

        return OperationResult()

class SetEmail(Operation):
    def __init__(self):
        Operation.__init__(self, { "user_id": int,
                                   "value": str })

    def process(self, db, user, user_id, value):
        if user.id != user_id and not user.hasRole(db, "administrator"):
            raise OperationFailure(code="notallowed",
                                   title="Not allowed!",
                                   message="Operation not permitted.")

        if not value.strip():
            raise OperationError("empty email address is not allowed")
        if value.count("@") != 1:
            raise OperationError("invalid email address")

        db.cursor().execute("UPDATE users SET email=%s WHERE id=%s", (value.strip(), user_id))
        db.commit()

        return OperationResult()

class SetGitEmails(Operation):
    def __init__(self):
        Operation.__init__(self, { "user_id": int,
                                   "value": [str] })

    def process(self, db, user, user_id, value):
        if user.id != user_id and not user.hasRole(db, "administrator"):
            raise OperationFailure(code="notallowed",
                                   title="Not allowed!",
                                   message="Operation not permitted.")

        for address in value:
            if not address.strip():
                raise OperationError("empty email address is not allowed")
            if address.count("@") != 1:
                raise OperationError("invalid email address")

        cursor = db.cursor()
        cursor.execute("SELECT email FROM usergitemails WHERE uid=%s", (user_id,))

        current_addresses = set(address for (address,) in cursor)
        new_addresses = set(address.strip() for address in value)

        for address in (current_addresses - new_addresses):
            cursor.execute("DELETE FROM usergitemails WHERE uid=%s AND email=%s", (user_id, address))
        for address in (new_addresses - current_addresses):
            cursor.execute("INSERT INTO usergitemails (uid, email) VALUES (%s, %s)", (user_id, address))

        db.commit()

        return OperationResult()

class ChangePassword(Operation):
    def __init__(self):
        Operation.__init__(self, { "user_id": int,
                                   "current_pw": Optional(str),
                                   "new_pw": str })

    def process(self, db, user, user_id, new_pw, current_pw=None):
        import auth

        if (user.id != user_id or current_pw is None) and not user.hasRole(db, "administrator"):
            raise OperationFailure(code="notallowed",
                                   title="Not allowed!",
                                   message="Operation not permitted.")

        subject = dbutils.User.fromId(db, user_id)

        if current_pw is not None:
            try: auth.checkPassword(db, subject.name, current_pw)
            except auth.WrongPassword:
                raise OperationFailure(code="wrongpassword",
                                       title="Wrong password!",
                                       message="The provided current password is not correct.")

        if not new_pw:
            raise OperationFailure(code="emptypassword",
                                   title="Empty password!",
                                   message="Setting an empty password is not allowed.")

        cursor = db.cursor()
        cursor.execute("UPDATE users SET password=%s WHERE id=%s", (auth.hashPassword(new_pw), user_id))

        db.commit()

        return OperationResult()
