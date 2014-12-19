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

    def getEffectiveUser(self, critic):
        if self.actual_user:
            return self.actual_user
        return api.user.anonymous(critic)

    def cached(self, cls, key, callback):
        wvd = self.__cache.setdefault(cls, weakref.WeakValueDictionary())
        try:
            value = wvd[key]
        except KeyError:
            value = wvd[key] = callback()
        assert isinstance(value, cls)
        return value

def startSession(allow_unsafe_cursors=True):
    return api.critic.Critic(Critic(dbutils.Database(allow_unsafe_cursors)))
