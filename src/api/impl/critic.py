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

class Critic(object):
    def __init__(self, database):
        self.database = database
        self.actual_user = None
        self.__cache = {}

        database.registerTransactionCallback(self.__refreshCache)

    def getEffectiveUser(self, critic):
        if self.actual_user:
            return self.actual_user
        return api.user.anonymous(critic)

    def cached(self, cls, key, create):
        wvd = self.__cache.setdefault(cls, weakref.WeakValueDictionary())
        try:
            value = wvd[key]
        except KeyError:
            value = wvd[key] = create()
        assert isinstance(value, cls)
        return value

    def __refreshCache(self, event):
        # |event| is either "commit" or "rollback".  In either case, we may have
        # stale values in our cache that we want to refresh at this point.
        for wvd in self.__cache.values():
            for value in wvd.values():
                value.refresh()
        return True

def startSession(for_user, for_system, for_testing):
    if for_user:
        db = dbutils.Database.forUser()
    elif for_system:
        db = dbutils.Database.forSystem()
    else:
        db = dbutils.Database.forTesting()
    return api.critic.Critic(Critic(db))
