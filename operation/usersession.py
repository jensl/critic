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

from operation import Operation, OperationResult, OperationError

import dbutils
import configuration
import auth
import os
import base64
import hashlib

class ValidateLogin(Operation):
    def __init__(self):
        Operation.__init__(self, { "username": str,
                                   "password": str },
                           accept_anonymous_user=True)

    def process(self, db, user, username, password):
        if not user.isAnonymous():
            if user.name == username:
                return OperationResult()
            else:
                return OperationResult(message="Already signed as '%s'!" % user.name)

        try: auth.checkPassword(db, username, password)
        except auth.NoSuchUser: return OperationResult(message="No such user!")
        except auth.WrongPassword: return OperationResult(message="Wrong password!")

        sid = base64.b64encode(hashlib.sha1(os.urandom(20)).digest())

        cursor = db.cursor()
        cursor.execute("""INSERT INTO usersessions (key, uid)
                               SELECT %s, id
                                 FROM users
                                WHERE name=%s""",
                       (sid, username))

        db.commit()

        return OperationResult().setCookie("sid", sid)

    def sanitize(self, value):
        sanitized = value.copy()
        sanitized["password"] = "****"
        return sanitized

class EndSession(Operation):
    def __init__(self):
        Operation.__init__(self, {})

    def process(self, db, user):
        if not user.isAnonymous():
            cursor = db.cursor()
            cursor.execute("DELETE FROM usersessions WHERE uid=%s", (user.id,))

            db.commit()

            return OperationResult().setCookie("sid")
