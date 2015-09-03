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
    def __init__(self, critic):
        self.critic = critic

        self.__atexit = []
        self.storage = { "Repository": {},
                         "User": {},
                         "Commit": {},
                         "CommitUserTime": {},
                         "Timezones": {} }
        self.profiling = {}
        self.pending_mails = []

        self.__user = None
        self.__authentication_labels = set()
        self.__profiles = set()

    def refresh(self):
        self.storage["User"].clear()

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

    @property
    def authentication_labels(self):
        return self.__authentication_labels

    @property
    def profiles(self):
        return frozenset(self.__profiles)

    def setUser(self, user, authentication_labels=()):
        import auth
        import api
        assert not self.__user or self.__user.isAnonymous()
        self.__user = user
        self.__authentication_labels.update(authentication_labels)
        self.__profiles.add(auth.AccessControlProfile.forUser(
            self, user, self.__authentication_labels))
        if self.critic and not (user.isAnonymous() or user.isSystem()):
            self.critic.setActualUser(api.user.fetch(self.critic, user_id=user.id))

    def addProfile(self, profile):
        self.__profiles.add(profile)

    def commit(self):
        if self.pending_mails:
            import mailutils
            mailutils.sendPendingMails(self.pending_mails)
            self.pending_mails = []

    def rollback(self):
        if self.pending_mails:
            import mailutils
            mailutils.cancelPendingMails(self.pending_mails)
            self.pending_mails = []
