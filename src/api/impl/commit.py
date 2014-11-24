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

import calendar
import datetime
import re

import api
import api.impl

import gitutils

RE_FOLLOWUP = re.compile("(fixup|squash)!.*(?:\n[ \t]*)+(.*)")

class Commit(object):
    def __init__(self, repository_id, internal):
        self.__repository_id = repository_id
        self.internal = internal
        self.sha1 = internal.sha1
        self.tree = internal.tree
        self.message = internal.message

    def getRepository(self, critic):
        return api.repository.fetch(critic, repository_id=self.__repository_id)

    def getId(self, critic):
        return self.internal.getId(critic.database)

    def getSummary(self):
        match = RE_FOLLOWUP.match(self.message)
        if match:
            followup_type, summary = match.groups()
            return "[%s] %s" % (followup_type, summary)
        return self.message.split("\n", 1)[0]

    def getParents(self, critic):
        return [fetch(self.getRepository(critic), sha1=sha1)
                for sha1 in self.internal.parents]

    def getDescription(self, critic):
        return self.internal.repository.describe(critic.database, self.sha1)

    def getAuthor(self, critic):
        return api.commit.Commit.UserAndTimestamp(
            self.internal.author.name,
            self.internal.author.email,
            datetime.datetime.fromtimestamp(
                calendar.timegm(self.internal.author.time)))

    def getCommitter(self, critic):
        return api.commit.Commit.UserAndTimestamp(
            self.internal.committer.name,
            self.internal.committer.email,
            datetime.datetime.fromtimestamp(
                calendar.timegm(self.internal.committer.time)))

    def isAncestorOf(self, commit):
        return self.internal.isAncestorOf(commit.internal)

    def wrap(self, critic):
        return api.commit.Commit(critic, self)

def fetch(repository, commit_id=None, sha1=None, ref=None):
    critic = repository.critic
    if ref is not None:
        sha1 = repository.resolveRef(ref, expect="commit")
    elif sha1 is None:
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT sha1
                            FROM commits
                           WHERE id=%s""",
                       (commit_id,))
        row = cursor.fetchone()
        if not row:
            raise api.commit.InvalidCommitId(commit_id)
        (sha1,) = row

    def callback():
        try:
            internal = gitutils.Commit.fromSHA1(
                db=critic.database,
                repository=repository._impl.getInternal(critic),
                sha1=sha1,
                commit_id=commit_id)
        except gitutils.GitReferenceError:
            raise api.commit.InvalidSHA1(sha1)
        return Commit(repository.id, internal).wrap(critic)

    return critic._impl.cached(api.commit.Commit, sha1, callback)
