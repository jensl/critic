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

        # Set 'sid' and 'has_sid' cookies.
        #
        # The 'has_sid' cookie is significant if the system is accessible over
        # both HTTP and HTTPS.  In that case, the 'sid' cookie is set with the
        # "secure" flag, so is only sent over HTTPS.  The 'has_sid' cookie is
        # then used to detect that an HTTP client would have sent a 'sid' cookie
        # if the request instead had been made over HTTPS, in which case we
        # redirect the client to HTTPS automatically.

        result = OperationResult()
        result.setCookie("sid", sid, secure=True)
        result.setCookie("has_sid", "1")
        return result

    def sanitize(self, value):
        sanitized = value.copy()
        sanitized["password"] = "****"
        return sanitized

class EndSession(Operation):
    def __init__(self):
        Operation.__init__(self, {})

    def process(self, db, user):
        cursor = db.cursor()
        cursor.execute("DELETE FROM usersessions WHERE uid=%s", (user.id,))

        db.commit()

        return OperationResult().setCookie("sid").setCookie("has_sid")
