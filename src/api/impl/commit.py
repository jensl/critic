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
from . import apiobject
import api.impl

import diff.parse
import gitutils

RE_FOLLOWUP = re.compile("(fixup|squash)!.*(?:\n[ \t]*)+(.*)")

class Commit(apiobject.APIObject):
    wrapper_class = api.commit.Commit

    def __init__(self, repository, internal):
        self.repository = repository
        self.internal = internal
        self.sha1 = internal.sha1
        self.tree = internal.tree
        self.message = internal.message

    def getId(self, critic):
        return self.internal.getId(critic.database)

    def getSummary(self):
        match = RE_FOLLOWUP.match(self.message)
        if match:
            followup_type, summary = match.groups()
            return "[%s] %s" % (followup_type, summary)
        return self.message.split("\n", 1)[0]

    def getParents(self, critic):
        return [fetch(self.repository, None, sha1, None)
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
        return self.internal.isAncestorOf(commit._impl.internal)

    def getFileInformation(self, file):
        import stat
        internal = self.internal.getFileEntry(file.path)
        if internal is None:
            return None
        if internal.type != "blob" or not stat.S_ISREG(internal.mode):
            raise api.commit.NotAFile(file.path)
        return api.commit.Commit.FileInformation(
            file, int(internal.mode), internal.sha1, internal.size)

    def getFileContents(self, file):
        information = self.getFileInformation(file)
        if information is None:
            return None
        return self.internal.repository.fetch(information.sha1).data

    def getFileLines(self, file):
        contents = self.getFileContents(file)
        if contents is None:
            return None
        return diff.parse.splitlines(contents)

    @staticmethod
    def create(critic, repository, commit_id, sha1):
        try:
            internal = gitutils.Commit.fromSHA1(
                db=critic.database,
                repository=repository._impl.getInternal(critic),
                sha1=sha1,
                commit_id=commit_id)
        except gitutils.GitReferenceError:
            raise api.commit.InvalidSHA1(sha1)
        return Commit(repository, internal).wrap(critic)

def fetch(repository, commit_id, sha1, ref):
    critic = repository.critic

    def commit_id_from_sha1():
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id
                            FROM commits
                           WHERE sha1=%s""",
                       (sha1,))
        row = cursor.fetchone()
        if not row:
            raise api.commit.InvalidSHA1(sha1)
        (commit_id,) = row
        return commit_id

    def sha1_from_commit_id():
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT sha1
                            FROM commits
                           WHERE id=%s""",
                       (commit_id,))
        row = cursor.fetchone()
        if not row:
            raise api.commit.InvalidCommitId(commit_id)
        (sha1,) = row
        return sha1

    if ref is not None:
        sha1 = repository.resolveRef(ref, expect="commit")

    if commit_id is not None:
        try:
            return Commit.get_cached(critic, (int(repository), commit_id))
        except KeyError:
            pass

        if sha1 is None:
            sha1 = sha1_from_commit_id()
    else:
        try:
            return Commit.get_cached(critic, (int(repository), sha1))
        except KeyError:
            pass

        commit_id = commit_id_from_sha1()

    commit = Commit.create(critic, repository, commit_id, sha1)

    Commit.add_cached(critic, (int(repository), commit_id), commit)
    Commit.add_cached(critic, (int(repository), sha1), commit)

    return commit

def fetchMany(repository, commit_ids, sha1s):
    critic = repository.critic
    cursor = critic.getDatabaseCursor()
    if commit_ids:
        cursor.execute(
            """SELECT id, sha1
                 FROM commits
                WHERE id=ANY (%s)""",
            (commit_ids,))

        rows = cursor.fetchall()
        if len(rows) != len(set(commit_ids)):
            found = set(commit_id for commit_id, _ in rows)
            for commit_id in commit_ids:
                if commit_id not in found:
                    raise api.commit.InvalidCommitId(commit_id)

        commits = {
            commit_id: sha1
            for commit_id, sha1 in rows
        }

        return [fetch(repository, commit_id, commits[commit_id], None)
                for commit_id in commit_ids]
    else:
        cursor.execute(
            """SELECT id, sha1
                 FROM commits
                WHERE sha1=ANY (%s)""",
            (sha1s,))

        rows = cursor.fetchall()
        if len(rows) != len(set(sha1s)):
            found = set(sha1 for _, sha1 in rows)
            for sha1 in sha1s:
                if sha1 not in found:
                    raise api.commit.InvalidSHA1(sha1)

        commits = {
            sha1: commit_id
            for commit_id, sha1 in rows
        }

        return [fetch(repository, commits[sha1], sha1, None)
                for sha1 in sha1s]
