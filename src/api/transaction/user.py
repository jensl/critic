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

    def createFilter(self, filter_type, repository, path, delegates):
        assert filter_type in ("reviewer", "watcher", "ignore")
        assert isinstance(repository, api.repository.Repository)
        assert all(isinstance(delegate, api.user.User)
                   for delegate in delegates)

        def fetchCreatedFilter(filter_id):
            return api.filters.fetchRepositoryFilter(
                self.transaction.critic, filter_id)

        self.transaction.tables.add("filters")
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO filters (uid, repository, path, type, delegate)
                   VALUES (%s, %s, %s, %s, %s)
                RETURNING id""",
                (self.user.id, repository.id, path, filter_type,
                 ",".join(delegate.name for delegate in delegates)),
                transform=fetchCreatedFilter))

    def modifyFilter(self, repository_filter):
        from filters import ModifyRepositoryFilter
        assert repository_filter.subject == self.user
        return ModifyRepositoryFilter(self.transaction, repository_filter)
