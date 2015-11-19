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
    def __init__(self, critic):
        self.critic = critic
        self.tables = set()
        self.items = []

    def modifyUser(self, subject):
        from user import ModifyUser
        assert isinstance(subject, api.user.User)
        api.PermissionDenied.raiseUnlessUser(self.critic, subject)
        return ModifyUser(self, subject)

    def modifyAccessToken(self, access_token):
        from accesstoken import ModifyAccessToken
        assert isinstance(access_token, api.accesstoken.AccessToken)
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessToken(self, access_token)

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
                item(self.critic, cursor)

class Query(object):
    def __init__(self, statement, *values, **kwargs):
        self.statement = statement
        self.__values = values
        self.collector = kwargs.get("collector")

    @property
    def values(self):
        for values in self.__values:
            yield [value.evaluate() if isinstance(value, LazyValue) else value
                   for value in values]

    def __call__(self, critic, cursor):
        if self.collector:
            for values in self.values:
                cursor.execute(self.statement, values)
                for row in cursor:
                    self.collector(*row)
        else:
            cursor.executemany(self.statement, self.values)

class LazyValue(object):
    def evaluate(self):
        raise Exception("LazyValue.evaluate() must be implemented!")
