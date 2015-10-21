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

import api.transaction

class ModifyRepositoryFilter(object):
    def __init__(self, transaction, repository_filter):
        self.transaction = transaction
        self.repository_filter = repository_filter

    def setDelegates(self, value):
        assert all(isinstance(delegate, api.user.User) for delegate in value)
        self.transaction.tables.add("filters")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE filters
                      SET delegate=%s
                    WHERE id=%s""",
                (",".join(delegate.name for delegate in value),
                 self.repository_filter.id)))

    def delete(self):
        self.transaction.tables.add("filters")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM filters
                    WHERE id=%s""",
                (self.repository_filter.id,)))
