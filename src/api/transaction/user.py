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

class ModifyUser(object):
    def __init__(self, transaction, user):
        self.transaction = transaction
        self.user = user

    def setFullname(self, value):
        self.transaction.tables.add("users")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE users
                      SET fullname=%s
                    WHERE id=%s""",
                (value, self.user.id)))

    # Repository filters
    # ==================

    def createFilter(self, filter_type, repository, path, delegates,
                     callback=None):
        assert filter_type in ("reviewer", "watcher", "ignore")
        assert isinstance(repository, api.repository.Repository)
        assert all(isinstance(delegate, api.user.User)
                   for delegate in delegates)

        def collectCreatedFilter(filter_id):
            if callback:
                callback(api.filters.fetchRepositoryFilter(
                    self.transaction.critic, filter_id))

        self.transaction.tables.add("filters")
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO filters (uid, repository, path, type, delegate)
                   VALUES (%s, %s, %s, %s, %s)
                RETURNING id""",
                (self.user.id, repository.id, path, filter_type,
                 ",".join(delegate.name for delegate in delegates)),
                collector=collectCreatedFilter))

    def modifyFilter(self, repository_filter):
        from .filters import ModifyRepositoryFilter
        assert repository_filter.subject == self.user
        return ModifyRepositoryFilter(self.transaction, repository_filter)

    # Access tokens
    # =============

    def createAccessToken(self, access_type, title, callback=None):
        import auth
        import base64

        from .accesstoken import CreatedAccessToken

        critic = self.transaction.critic

        if access_type != "user":
            api.PermissionDenied.raiseUnlessAdministrator(critic)

        user_id = self.user.id if access_type == "user" else None

        part1 = auth.getToken(encode=base64.b64encode, length=12)
        part2 = auth.getToken(encode=base64.b64encode, length=21)

        access_token = CreatedAccessToken(
            critic, self.user if access_type == "user" else None, callback)

        self.transaction.tables.update(("accesstokens",
                                        "accesscontrolprofiles"))
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO accesstokens (access_type, uid, part1, part2, title)
                   VALUES (%s, %s, %s, %s, %s)
                RETURNING id""",
                (access_type, user_id, part1, part2, title),
                collector=access_token))
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO accesscontrolprofiles (access_token)
                   VALUES (%s)
                RETURNING id""",
                (access_token,),
                collector=access_token.profile))

        return access_token

    def modifyAccessToken(self, access_token):
        from .accesstoken import ModifyAccessToken
        assert access_token.user == self.user

        critic = self.transaction.critic

        if critic.access_token and critic.access_token == access_token:
            # Don't allow any modifications of the access token used to
            # authenticate.  This could for instance be used to remove the
            # access restrictions of the token, which would obviously be bad.
            raise api.PermissionDenied("Access token used to authenticate")

        return ModifyAccessToken(self.transaction, access_token)
