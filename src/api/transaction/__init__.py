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

class Transaction(object):
    def __init__(self, critic, result=None):
        self.critic = critic
        self.tables = set()
        self.items = []
        self.result = [] if result is None else result

    def modifyUser(self, subject):
        from user import ModifyUser
        assert isinstance(subject, api.user.User)
        api.PermissionDenied.raiseUnlessUser(self.critic, subject)
        return ModifyUser(self, subject)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and exc_val is None and exc_tb is None:
            self.__commit()
        return False

    def __commit(self):
        if not self.items:
            return
        with self.critic.getUpdatingDatabaseCursor(*self.tables) as cursor:
            for item in self.items:
                self.result.append(item(self.critic, cursor))

class Query(object):
    def __init__(self, statement, *values, **kwargs):
        self.statement = statement
        self.values = values
        self.transform = kwargs.get("transform")

    def __call__(self, critic, cursor):
        if self.transform:
            assert len(self.values) == 1
            cursor.execute(self.statement, self.values[0])
            return self.transform(*cursor.fetchone())
        cursor.executemany(self.statement, self.values)
