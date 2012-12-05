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

import gitutils

class Branch(object):
    def __init__(self, id, repository, name, head, base, tail, branch_type, review_id):
        self.id = id
        self.repository = repository
        self.name = name
        self.head = head
        self.base = base
        self.tail = tail
        self.type = branch_type
        self.review_id = review_id
        self.review = None
        self.commits = None

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def contains(self, db, commit):
        cursor = db.cursor()
        if isinstance(commit, gitutils.Commit) and commit.id is not None:
            cursor.execute("SELECT 1 FROM reachable WHERE branch=%s AND commit=%s", [self.id, commit.id])
        else:
            cursor.execute("SELECT 1 FROM reachable, commits WHERE branch=%s AND commit=id AND sha1=%s", [self.id, str(commit)])
        return cursor.fetchone() is not None

    def getJSConstructor(self):
        from htmlutils import jsify
        if self.base:
            return "new Branch(%d, %s, %s)" % (self.id, jsify(self.name), self.base.getJSConstructor())
        else:
            return "new Branch(%d, %s, null)" % (self.id, jsify(self.name))

    def getJS(self):
        return "var branch = %s;" % self.getJSConstructor()

    def loadCommits(self, db):
        if self.commits is None:
            cursor = db.cursor()
            cursor.execute("SELECT commits.id, commits.sha1 FROM reachable, commits WHERE reachable.branch=%s AND reachable.commit=commits.id", [self.id])
            self.commits = []
            for commit_id, sha1 in cursor:
                self.commits.append(gitutils.Commit.fromSHA1(db, self.repository, sha1, commit_id=commit_id))

    def rebase(self, db, base):
        cursor = db.cursor()

        def findReachable(head, base_branch_id, force_include=set()):
            bases = [base_branch_id]

            while True:
                cursor.execute("SELECT base FROM branches WHERE id=%s", (bases[-1],))
                branch_id = cursor.fetchone()[0]
                if branch_id is None: break
                bases.append(branch_id)

            expression = "SELECT 1 FROM reachable, commits WHERE branch IN (%s) AND commit=id AND sha1=%%s" % ", ".join(["%s"] * len(bases))

            def exclude(sha1):
                cursor.execute(expression, bases + [sha1])
                return cursor.fetchone() is not None

            stack = [head.sha1]
            processed = set()
            values = []

            while stack:
                sha1 = stack.pop(0)

                if sha1 not in processed:
                    processed.add(sha1)

                    commit = gitutils.Commit.fromSHA1(db, self.repository, sha1)

                    if sha1 in force_include or not exclude(sha1):
                        values.append(commit.getId(db))

                        for sha1 in commit.parents:
                            if sha1 not in processed and (sha1 in force_include or not exclude(sha1)):
                                stack.append(sha1)

            return values

        cursor.execute("SELECT COUNT(*) FROM reachable WHERE branch=%s", (self.id,))
        old_count = cursor.fetchone()[0]

        if base.base and base.base.id == self.id:
            self.loadCommits(db)

            cursor.execute("SELECT count(*) FROM reachable WHERE branch=%s", (base.id,))
            base_old_count = cursor.fetchone()[0]

            base_reachable = findReachable(base.head, self.base.id, set([commit.sha1 for commit in self.commits]))
            base_new_count = len(base_reachable)

            cursor.execute("DELETE FROM reachable WHERE branch=%s", [base.id])
            cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", [(base.id, commit) for commit in base_reachable])
            cursor.execute("UPDATE branches SET base=%s WHERE id=%s", [self.base.id, base.id])

            base.base = self.base
            base.commits = None
        else:
            base_old_count = None
            base_new_count = None

        our_reachable = findReachable(self.head, base.id)
        new_count = len(our_reachable)

        cursor.execute("DELETE FROM reachable WHERE branch=%s", [self.id])
        cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", [(self.id, commit) for commit in our_reachable])
        cursor.execute("UPDATE branches SET base=%s WHERE id=%s", [base.id, self.id])

        self.base = base
        self.commits = None

        return old_count, new_count, base_old_count, base_new_count

    @staticmethod
    def fromId(db, branch_id, load_review=False, load_commits=True, profiler=None):
        cursor = db.cursor()
        cursor.execute("SELECT name, repository, head, base, tail, branches.type, review, reviews.id IS NOT NULL FROM branches LEFT OUTER JOIN reviews ON (branches.id=reviews.branch) WHERE branches.id=%s", [branch_id])
        row = cursor.fetchone()

        if not row: return None
        else:
            branch_name, repository_id, head_commit_id, base_branch_id, tail_commit_id, type, review_id, has_review = row

            if profiler: profiler.check("Branch.fromId: basic")

            repository = gitutils.Repository.fromId(db, repository_id)

            if profiler: profiler.check("Branch.fromId: repository")

            if load_commits:
                try: head_commit = gitutils.Commit.fromId(db, repository, head_commit_id)
                except: head_commit = None

                if profiler: profiler.check("Branch.fromId: head")
            else:
                head_commit = None

            if load_commits:
                base_branch = Branch.fromId(db, base_branch_id) if base_branch_id is not None else None

                if profiler: profiler.check("Branch.fromId: base")

                tail_commit = gitutils.Commit.fromId(db, repository, tail_commit_id) if tail_commit_id is not None else None

                if profiler: profiler.check("Branch.fromId: tail")
            else:
                base_branch = None
                tail_commit = None

            branch = Branch(branch_id, repository, branch_name, head_commit, base_branch, tail_commit, type, review_id)

            if has_review and load_review:
                from dbutils import Review

                branch.review = Review.fromBranch(db, branch)

                if profiler: profiler.check("Branch.fromId: review")

            return branch

    @staticmethod
    def fromName(db, repository, name):
        cursor = db.cursor()
        cursor.execute("SELECT id FROM branches WHERE repository=%s AND name=%s", (repository.id, name))
        row = cursor.fetchone()
        if not row: return None
        else: return Branch.fromId(db, row[0])
