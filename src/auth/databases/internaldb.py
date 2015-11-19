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

if configuration.auth.DATABASE == "internal":
    auth.DATABASE = Internal()
