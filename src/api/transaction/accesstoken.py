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

class ModifyAccessToken(object):
    def __init__(self, transaction, access_token):
        self.transaction = transaction
        self.access_token = access_token

    def setTitle(self, value):
        self.transaction.tables.add("accesstokens")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE accesstokens
                      SET title=%s
                    WHERE id=%s""",
                (value, self.access_token.id)))

    def delete(self):
        self.transaction.tables.add("accesstokens")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM accesstokens
                    WHERE id=%s""",
                (self.access_token.id,)))

    def modifyProfile(self):
        from .accesscontrolprofile import ModifyAccessControlProfile
        assert self.access_token.profile
        return ModifyAccessControlProfile(
            self.transaction, self.access_token.profile)

class CreatedAccessToken(api.transaction.LazyAPIObject):
    def __init__(self, critic, user, callback=None):
        from .accesscontrolprofile import CreatedAccessControlProfile
        super(CreatedAccessToken, self).__init__(
            critic, api.accesstoken.fetch, callback)
        self.user = user
        self.profile = CreatedAccessControlProfile(critic, self)
