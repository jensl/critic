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

import weakref

import api
import dbutils

class NoKey(object):
    pass

class Critic(object):
    def __init__(self):
        self.database = None
        self.actual_user = None
        self.access_token = None
        self.__cache = {}

    def setDatabase(self, database):
        database.registerTransactionCallback(self.__refreshCache)
        self.database = database

    def getEffectiveUser(self, critic):
        if self.actual_user:
            return self.actual_user
        return api.user.anonymous(critic)

    def lookup(self, cls, key=NoKey):
        objects = self.__cache[cls]
        if key is NoKey:
            return objects
        return objects[key]

    def assign(self, cls, key, value):
        self.__cache.setdefault(cls, weakref.WeakValueDictionary())[key] = value

    def __refreshCache(self, event):
        # |event| is either "commit" or "rollback".  In either case, we may have
        # stale values in our cache that we want to refresh at this point.
        for wvd in self.__cache.values():
            for value in wvd.values():
                value.refresh()
        return True

def startSession(for_user, for_system, for_testing):
    critic = api.critic.Critic(Critic())

    if for_user:
        database = dbutils.Database.forUser(critic)
    elif for_system:
        database = dbutils.Database.forSystem(critic)
    else:
        database = dbutils.Database.forTesting(critic)

    critic._impl.setDatabase(database)
    return critic
