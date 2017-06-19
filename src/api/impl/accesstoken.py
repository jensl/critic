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

import api
import apiobject

class AccessToken(apiobject.APIObject):
    wrapper_class = api.accesstoken.AccessToken

    def __init__(self, token_id, access_type, user_id, part1, part2, title):
        self.id = token_id
        self.access_type = access_type
        self.__user_id = user_id
        self.part1 = part1
        self.part2 = part2
        self.title = title
        self.__profile_id = None

    def getUser(self, critic):
        if self.__user_id is None:
            return None
        return api.user.fetch(critic, self.__user_id)

    def getProfile(self, critic):
        if self.__profile_id is None:
            cursor = critic.getDatabaseCursor()
            cursor.execute("""SELECT id
                                FROM accesscontrolprofiles
                               WHERE access_token=%s""",
                           (self.id,))
            row = cursor.fetchone()
            if not row:
                return None
            self.__profile_id, = row
        return api.accesscontrolprofile.fetch(critic, self.__profile_id)

    def refresh(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, access_type, uid, part1, part2, title
                            FROM accesstokens
                           WHERE id=%s""",
                       (self.id,))
        for row in cursor:
            return AccessToken(*row)
        return self

@AccessToken.cached()
def fetch(critic, token_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute(
        """SELECT id, access_type, uid, part1, part2, title
             FROM accesstokens
            WHERE id=%s""",
        (token_id,))
    try:
        return next(AccessToken.make(critic, cursor))
    except StopIteration:
        raise api.accesstoken.InvalidAccessTokenId(token_id)

def fetchAll(critic, user):
    cursor = critic.getDatabaseCursor()
    if user is None:
        cursor.execute(
            """SELECT id, access_type, uid, part1, part2, title
                 FROM accesstokens""")
    else:
        cursor.execute(
            """SELECT id, access_type, uid, part1, part2, title
                 FROM accesstokens
                WHERE uid=%s""",
            (user.id,))
    return list(AccessToken.make(critic, cursor))
