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
import dbutils

class AccessTokens(auth.Database):
    def __init__(self, authdb):
        super(AccessTokens, self).__init__("accesstokens")
        self.authdb = authdb

    def getFields(self):
        return self.authdb.getFields()

    def authenticate(self, db, fields):
        self.authdb.authenticate(db, fields)

    def getAuthenticationLabels(self, user):
        return self.authdb.getAuthenticationLabels(user)

    def supportsHTTPAuthentication(self):
        # HTTP authentication is the primary use-case.
        return True

    def performHTTPAuthentication(self, db, username, password):
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT id, access_type, uid
                            FROM accesstokens
                           WHERE part1=%s
                             AND part2=%s""",
                       (username, password))
        row = cursor.fetchone()

        if row:
            token_id, access_type, user_id = row

            if access_type == "anonymous":
                db.setUser(dbutils.User.makeAnonymous())
            elif access_type == "system":
                db.setUser(dbutils.User.makeSystem())
            else:
                user = dbutils.User.fromId(db, user_id)
                authentication_labels = self.getAuthenticationLabels(user)
                db.setUser(user, authentication_labels)

            import api
            db.critic.setAccessToken(api.accesstoken.fetch(db.critic, token_id))

            cursor.execute("""SELECT id
                                FROM accesscontrolprofiles
                               WHERE access_token=%s""",
                           (token_id,))
            row = cursor.fetchone()

            if row:
                profile_id, = row
                db.addProfile(auth.AccessControlProfile.fromId(db, profile_id))

            return

        return self.authdb.performHTTPAuthentication(db, username, password)

    def supportsPasswordChange(self):
        return self.authdb.supportsPasswordChange()

    def changePassword(self, db, user, current_pw, new_pw):
        if db.critic.access_token is not None:
            raise auth.AccessDenied
        return self.authdb.changePassword(db, user, current_pw, new_pw)

if configuration.auth.ENABLE_ACCESS_TOKENS:
    auth.DATABASE = AccessTokens(auth.DATABASE)
