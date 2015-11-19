# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

class Session(object):
    def __init__(self):
        self.__atexit = []
        self.storage = { "Repository": {},
                         "User": {},
                         "Commit": {},
                         "CommitUserTime": {},
                         "Timezones": {} }
        self.profiling = {}

        self.__user = None

    def atexit(self, fn):
        self.__atexit.append(fn)

    def close(self):
        for fn in self.__atexit:
            try: fn(self)
            except: pass
        self.__atexit = []

    def disableProfiling(self):
        self.profiling = None

    def recordProfiling(self, item, duration, rows=None, repetitions=1):
        if self.profiling is not None:
            count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows = self.profiling.get(item, (0, 0.0, 0.0, None, None))

            count += repetitions
            accumulated_ms += 1000 * duration
            maximum_ms = max(maximum_ms, 1000 * duration)

            if rows is not None:
                if accumulated_rows is None: accumulated_rows = 0
                if maximum_rows is None: maximum_rows = 0
                accumulated_rows += rows
                maximum_rows = max(maximum_rows, rows)

            self.profiling[item] = count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows

    @property
    def user(self):
        return self.__user

    def setUser(self, user):
        import auth
        assert not self.__user or self.__user.isAnonymous()
        self.__user = user
