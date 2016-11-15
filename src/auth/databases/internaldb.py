# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import auth
import configuration

class Internal(auth.Database):
    def __init__(self):
        super(Internal, self).__init__("internal")

    def getFields(self):
        return [(False, "username", "Username:"),
                (True, "password", "Password:")]

    def authenticate(self, db, values):
        username = values["username"].strip()
        if not username:
            raise auth.database.AuthenticationFailed("Empty username")
        password = values["password"]
        if not password:
            raise auth.database.AuthenticationFailed("Empty password")

        try:
            db.setUser(auth.checkPassword(db, username, password))
        except auth.NoSuchUser:
            raise auth.AuthenticationFailed("Invalid username")
        except auth.WrongPassword:
            raise auth.AuthenticationFailed("Wrong password")

    def supportsPasswordChange(self):
        return True

    def changePassword(self, db, user, current_pw, new_pw):
        # If |current_pw| is True, then this is an administrator changing
        # another user's password. The usual rules do not apply.
        if current_pw is not True:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT password FROM users WHERE id=%s", (user.id,))

            hashed_pw, = cursor.fetchone()

            if current_pw is not None:
                auth.checkPassword(db, user.name, current_pw)
            elif hashed_pw is not None:
                # This is mostly a sanity check; the only way to trigger this is
                # if the user has no password when he loads /home, sets a
                # password in another tab or using another browser, and then
                # tries to set (rather than change) the password using the old
                # stale /home.
                raise auth.WrongPassword

        with db.updating_cursor("users") as cursor:
            cursor.execute("UPDATE users SET password=%s WHERE id=%s",
                           (auth.hashPassword(new_pw), user.id))

if configuration.auth.DATABASE == "internal":
    auth.DATABASE = Internal()
