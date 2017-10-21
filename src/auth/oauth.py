# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import urllib

import dbutils
import auth
import textutils
import request

class OAuthProvider(auth.Provider):
    def start(self, db, req, target_url=None):
        state = auth.getToken()

        authorize_url = self.getAuthorizeURL(state)

        if authorize_url is None:
            return None

        if target_url is None:
            target_url = req.getParameter("target", None)

        with db.updating_cursor("oauthstates") as cursor:
            cursor.execute("""INSERT INTO oauthstates (state, url)
                                   VALUES (%s, %s)""",
                           (state, target_url))

        return authorize_url

    def finish(self, db, req):
        if req.method != "GET":
            raise auth.InvalidRequest

        code = req.getParameter("code", default=None)
        state = req.getParameter("state", default=None)

        if code is None or state is None:
            raise auth.InvalidRequest("Missing parameter(s)")

        cursor = db.cursor()
        cursor.execute("""SELECT url
                            FROM oauthstates
                           WHERE state=%s""",
                       (state,))

        row = cursor.fetchone()

        if not row:
            raise auth.InvalidRequest("Invalid OAuth state: %s" % state)

        (target_url,) = row

        access_token = self.getAccessToken(code)

        if access_token is None:
            raise auth.Failure("failed to get access token")

        user_data = self.getUserData(access_token)

        if user_data is None:
            raise auth.Failure("failed to get user data")

        account = textutils.encode(user_data["account"])
        username = textutils.encode(user_data["username"])
        email = user_data["email"]
        email = textutils.encode(email) if email else None
        fullname = textutils.encode(user_data.get("fullname", username))

        cursor.execute("""SELECT id, uid
                            FROM externalusers
                           WHERE provider=%s
                             AND account=%s""",
                       (self.name, account))

        row = cursor.fetchone()

        if row:
            external_user_id, user_id = row
        else:
            with db.updating_cursor("externalusers") as updating_cursor:
                updating_cursor.execute(
                    """INSERT INTO externalusers (provider, account, email)
                            VALUES (%s, %s, %s)
                         RETURNING id""",
                    (self.name, account, email))
                external_user_id, = updating_cursor.fetchone()
                user_id = None

        user = None

        if user_id is not None:
            user = dbutils.User.fromId(db, user_id)
        else:
            if auth.isValidUserName(username) \
                    and self.configuration.get("bypass_createuser"):
                try:
                    dbutils.User.fromName(db, username)
                except dbutils.NoSuchUser:
                    user = dbutils.User.create(
                        db, username, fullname, email, email_verified=None,
                        external_user_id=external_user_id)
                    user.sendUserCreatedMail("wsgi[oauth/%s]" % self.name,
                                             { "provider": self.name,
                                               "account": account })

        if user is None:
            token = auth.getToken()

            with db.updating_cursor("externalusers") as updating_cursor:
                updating_cursor.execute(
                    """UPDATE externalusers
                          SET token=%s
                        WHERE id=%s""",
                    (token, external_user_id))

            data = { "provider": self.name,
                     "account": account,
                     "token": token }

            if target_url:
                data["target"] = target_url
            if username:
                data["username"] = username
            if email:
                data["email"] = email
            if fullname:
                data["fullname"] = fullname

            target_url = "/createuser?%s" % urllib.parse.urlencode(data)

        if user is not None:
            auth.createSessionId(db, req, user)

        raise request.Found(target_url or "/")

    def validateToken(self, db, account, token):
        cursor = db.cursor()
        cursor.execute("""SELECT token
                            FROM externalusers
                           WHERE provider=%s
                             AND account=%s""",
                       (self.name, account))
        row = cursor.fetchone()
        return row and token == row[0]
