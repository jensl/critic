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

class InvalidUpdate(Exception):
    def __init__(self, expected_old_sha1, actual_old_sha1):
        super(InvalidUpdate, self).__init__(
            "Update old value mismatch: expected=%s, actual=%s"
            % (expected_old_sha1, actual_old_sha1))

class Branch(object):
    @staticmethod
    def isReviewBranch(db, repository, name):
        return name.startswith("r/")

    def __init__(self, id, repository, name, base_id, head, tail, branch_type, archived):
        self.id = id
        self.repository = repository
        self.name = name
        self.base_id = base_id
        self.head_id, self.head_sha1 = head
        self.tail_id, self.tail_sha1 = tail
        self.type = branch_type
        self.archived = archived
        self.review = None
        self.is_review_branch = branch_type == 'review'
        self.__commits = None
        self.__base = None
        self.__head = None
        self.__tail = None

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def contains(self, db, commit):
        import gitutils
        cursor = db.readonly_cursor()
        if isinstance(commit, gitutils.Commit) and commit.id is not None:
            cursor.execute("SELECT 1 FROM branchcommits WHERE branch=%s AND commit=%s", [self.id, commit.id])
        else:
            cursor.execute("SELECT 1 FROM branchcommits, commits WHERE branch=%s AND commit=id AND sha1=%s", [self.id, str(commit)])
        return cursor.fetchone() is not None

    def getBase(self, db):
        if self.__base is None and self.base_id is not None:
            self.__base = Branch.fromId(db, self.base_id)
        return self.__base

    def getHead(self, db):
        import gitutils
        if not self.__head:
            self.__head = gitutils.Commit.fromSHA1(db, self.repository, self.head_sha1, self.head_id)
        return self.__head

    def getTail(self, db):
        import gitutils
        if not self.__tail:
            if self.tail_id is None:
                return None
            self.__tail = gitutils.Commit.fromSHA1(db, self.repository, self.tail_sha1, self.tail_id)
        return self.__tail

    def getJSConstructor(self, db):
        from htmlutils import jsify
        if self.base_id is not None:
            base = self.getBase(db).getJSConstructor(db)
        else:
            base = "null"
        return "new Branch(%d, %s, %s)" % (self.id, jsify(self.name), base)

    def getJS(self, db):
        return "var branch = %s;" % self.getJSConstructor(db)

    def getCommits(self, db):
        import gitutils
        if self.__commits is None:
            cursor = db.readonly_cursor()
            cursor.execute("""SELECT commits.id, commits.sha1
                                FROM branchcommits
                                JOIN commits ON (commits.id=branchcommits.commit)
                               WHERE branchcommits.branch=%s""",
                           (self.id,))
            self.__commits = [gitutils.Commit.fromSHA1(db, self.repository, sha1, commit_id=commit_id)
                              for commit_id, sha1 in cursor]
        return self.__commits

    def rebase(self, db, user, base):
        import gitutils

        cursor = db.cursor()

        def findReachable(head, base_branch_id, force_include=set()):
            bases = [base_branch_id]

            while True:
                cursor.execute(
                    """SELECT base
                         FROM branches
                        WHERE id=%s""",
                    (bases[-1],))
                branch_id, = cursor.fetchone()
                if branch_id is None:
                    break
                bases.append(branch_id)

            def exclude(sha1):
                cursor.execute(
                    """SELECT 1
                         FROM branchcommits
                         JOIN commits ON (commits.id=branchcommits.commit)
                        WHERE branchcommits.branch=ANY (%s)
                          AND commits.sha1=%s""",
                    (bases, sha1))
                return cursor.fetchone() is not None

            stack = [head.sha1]
            processed = set()
            commit_ids = set()
            tail = None

            while stack:
                sha1 = stack.pop(0)

                if sha1 in processed:
                    continue

                processed.add(sha1)

                commit = gitutils.Commit.fromSHA1(db, self.repository, sha1)

                if sha1 not in force_include:
                    if exclude(sha1):
                        if tail is None:
                            tail = commit
                        continue

                commit_ids.add(commit.getId(db))

                for sha1 in commit.parents:
                    if sha1 not in processed:
                        stack.append(sha1)

            return commit_ids, tail

        def insertBranchUpdate(branch_id, head_id,
                               old_base_id, new_base_id,
                               old_commit_ids, new_commit_ids,
                               old_tail_id, new_tail_id):
            cursor.execute(
                """INSERT
                     INTO branchupdates (branch, updater, from_head, to_head,
                                         from_base, to_base, from_tail, to_tail)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id""",
                (branch_id, user.id, head_id, head_id,
                 old_base_id, new_base_id, old_tail_id, new_tail_id))

            branchupdate_id, = cursor.fetchone()

            associated_commit_ids = new_commit_ids - old_commit_ids
            disassociated_commit_ids = old_commit_ids - new_commit_ids

            cursor.executemany(
                """INSERT
                     INTO branchupdatecommits (branchupdate, commit, associated)
                   VALUES (%s, %s, %s)""",
                [(branchupdate_id, commit_id, True)
                 for commit_id in associated_commit_ids] +
                [(branchupdate_id, commit_id, False)
                 for commit_id in disassociated_commit_ids])

            cursor.execute(
                """DELETE
                     FROM branchcommits
                    WHERE branch=%s
                      AND commit=ANY (%s)""",
                (branch_id, list(disassociated_commit_ids)))
            cursor.executemany(
                """INSERT
                     INTO branchcommits (branch, commit)
                   VALUES (%s, %s)""",
                [(branch_id, commit_id) for commit_id in associated_commit_ids])
            cursor.execute(
                """UPDATE branches
                      SET base=%s,
                          tail=%s
                    WHERE id=%s""",
                (new_base_id, new_tail_id, branch_id))

        cursor.execute(
            """SELECT commit
                 FROM branchcommits
                WHERE branch=%s""",
            (self.id,))
        old_commit_ids = set(commit_id for commit_id, in cursor)
        old_count = len(old_commit_ids)

        if base.base_id == self.id:
            cursor.execute(
                """SELECT commit
                     FROM branchcommits
                    WHERE branch=%s""",
                (base.id,))
            base_old_commit_ids = set(commit_id for commit_id, in cursor)
            base_old_count = len(base_old_commit_ids)

            base_new_commit_ids, base_new_tail = findReachable(
                base.getHead(db), self.base_id,
                set(commit.sha1 for commit in self.getCommits(db)))
            base_new_count = len(base_new_commit_ids)

            insertBranchUpdate(base.id, base.head_id,
                               base.base_id, self.base_id,
                               base_old_commit_ids, base_new_commit_ids,
                               base.tail_id, base_new_tail.getId(db))

            base.base_id = self.base_id
            base.__base = self.__base
            base.__commits = None
        else:
            base_old_count = None
            base_new_count = None

        new_commit_ids, new_tail = findReachable(self.getHead(db), base.id)
        new_count = len(new_commit_ids)

        insertBranchUpdate(self.id, self.head_id,
                           self.base_id, base.id,
                           old_commit_ids, new_commit_ids,
                           self.tail_id, new_tail.getId(db))

        self.base_id = base.id
        self.tail_id = new_tail.getId(db)
        self.__base = base
        self.__commits = None

        return old_count, new_count, base_old_count, base_new_count

    def archive(self, db):
        import gitutils

        try:
            head = self.getHead(db)
        except gitutils.GitReferenceError:
            # The head commit appears to be missing from the repository.
            head = None
        else:
            self.repository.keepalive(head.sha1)

        if head:
            try:
                self.repository.deleteref("refs/heads/" + self.name, head)
            except gitutils.GitError:
                # Branch either doesn't exist, or points to the wrong commit.
                try:
                    sha1 = self.repository.revparse("refs/heads/" + self.name)
                except gitutils.GitReferenceError:
                    # Branch doesn't exist.  Pretend it's been archived already.
                    pass
                else:
                    # Branch points to the wrong commit.  Don't delete the ref.
                    return

        cursor = db.cursor()
        cursor.execute("""UPDATE branches
                             SET archived=TRUE
                           WHERE id=%s""",
                       (self.id,))

        self.archived = True

    def resurrect(self, db):
        self.repository.createref("refs/heads/" + self.name, self.getHead(db))

        cursor = db.cursor()
        cursor.execute("""UPDATE branches
                             SET archived=FALSE
                           WHERE id=%s""",
                       (self.id,))

        self.archived = False

    def validateUpdate(self, db, user, from_sha1, to_sha1, flags):
        trackedbranch_id = flags.get("trackedbranch_id")
        if trackedbranch_id:
            # This seems to be an update of a tracked branch by the branch
            # tracker service.
            #
            # First, double-check that the tracked branch id is correct.
            cursor = db.readonly_cursor()
            cursor.execute(
                """SELECT forced
                     FROM trackedbranches
                    WHERE id=%s
                      AND repository=%s
                      AND local_name=%s""",
                (trackedbranch_id, self.repository.id, self.name))
            row = cursor.fetchone()
            if not row:
                return "invalid tracked branch id"

    @staticmethod
    def revertUpdate(db, branchupdate_id, reverting_rebase=False):
        import gitutils

        cursor = db.readonly_cursor()
        cursor.execute("""SELECT branch,
                                 from_base, to_base,
                                 from_head, to_head,
                                 from_tail, to_tail,
                                 review
                            FROM branchupdates
                 LEFT OUTER JOIN reviewupdates ON (branchupdate=id)
                           WHERE id=%s""",
                       (branchupdate_id,))
        (branch_id,
         from_base_id, to_base_id,
         from_head_id, to_head_id,
         from_tail_id, to_tail_id,
         review_id) = cursor.fetchone()

        # If there is a review update record, everything apparently finished,
        # and we should have no reason to revert the update.
        assert review_id is None or reverting_rebase

        cursor.execute("""SELECT repository, name, head
                            FROM branches
                           WHERE id=%s""",
                       (branch_id,))
        repository_id, branch_name, current_head_id = cursor.fetchone()

        assert to_head_id == current_head_id

        repository = gitutils.Repository.fromId(db, repository_id)

        cursor.execute("""SELECT MAX(id)
                            FROM branchupdates
                           WHERE branch=%s""",
                       (branch_id,))
        latest_branchupdate_id, = cursor.fetchone()

        assert branchupdate_id == latest_branchupdate_id

        to_head = gitutils.Commit.fromId(db, repository, to_head_id)

        if from_head_id is None:
            # Branch was created, so we should just delete it.

            assert not reverting_rebase

            cursor.execute("""SELECT id
                                FROM reviews
                               WHERE branch=%s""",
                           (branch_id,))
            row = cursor.fetchone()
            tables = ["branches"]

            if row:
                review_id, = row
                tables.append("reviews")
            else:
                review_id = None

            with db.updating_cursor(*tables) as cursor:
                if review_id is not None:
                    cursor.execute("""DELETE
                                        FROM reviews
                                       WHERE id=%s""",
                                   (review_id,))

                cursor.execute("""DELETE
                                    FROM branches
                                   WHERE id=%s""",
                               (branch_id,))

                def finish(event):
                    if event == "commit":
                        repository.deleteref(
                            "refs/heads/%s" % branch_name,
                            to_head.sha1)

                db.registerTransactionCallback(finish)

            return

        from_head = gitutils.Commit.fromId(db, repository, from_head_id)

        cursor.execute("""SELECT commit, associated
                            FROM branchupdatecommits
                           WHERE branchupdate=%s""",
                       (branchupdate_id,))

        associated_commit_ids = []
        disassociated_commit_ids = []

        for commit_id, associated in cursor:
            if associated:
                associated_commit_ids.append(commit_id)
            else:
                disassociated_commit_ids.append(commit_id)

        with db.updating_cursor("branches",
                                "branchupdates",
                                "branchcommits") as cursor:
            # Revert the changes made to |branches| for this update.
            cursor.execute(
                """UPDATE branches
                      SET base=%s,
                          head=%s,
                          tail=%s
                    WHERE id=%s""",
                (from_base_id, from_head_id, from_tail_id, branch_id))

            # Revert the changes made to |branchcommits| for this update.
            cursor.executemany(
                """DELETE
                     FROM branchcommits
                    WHERE branch=%s
                      AND commit=%s""",
                ((branch_id, commit_id)
                 for commit_id in associated_commit_ids))
            cursor.executemany(
                """INSERT
                     INTO branchcommits (branch, commit)
                   VALUES (%s, %s)""",
                ((branch_id, commit_id)
                 for commit_id in disassociated_commit_ids))

            # Delete the update.
            cursor.execute(
                """DELETE
                     FROM branchupdates
                    WHERE id=%s""",
                (branchupdate_id,))

            def reset_ref(event):
                if event == "commit":
                    repository.updateref(
                        "refs/heads/%s" % branch_name,
                        from_head.sha1, to_head.sha1)

            # If this is a revert of a rebase, also reset the ref. If this is a
            # revert of a failed branch update, the ref is reset by the githook
            # background service.
            if reverting_rebase:
                db.registerTransactionCallback(reset_ref)

    @staticmethod
    def findBaseBranch(db, head, exclude_branches=[]):
        """Find base branch of a (new) branch at |head|

           Return the id of the base branch, as well as the id of the tail
           commit (the branch point) and the set of commits to associate with
           the new branch.

           If no base branch is found, the base branch id and tail commit id are
           None and the set of commits contain all commits reachable from
           |head|.

           If |head| is associated with the base branch, then the tail commit is
           |head|, and an empty set of commits is returned."""
        import gitutils
        import log.commitset

        cursor = db.readonly_cursor()
        repository = head.repository
        stack = [head.sha1]
        processed = set()

        base_branch_id = None
        tail = None
        commits = set()

        # Do a first-parent-first, depth-first search for a commit associated
        # with another branch.  The oldest (first created) such branch found
        # will be recorded as this branch's base branch, and that commit will be
        # its tail commit.
        while stack:
            commit = gitutils.Commit.fromSHA1(db, repository, stack.pop())

            if commit in processed:
                continue
            processed.add(commit)

            cursor.execute(
                """SELECT MIN(branches.id)
                     FROM branches
                     JOIN branchcommits ON (branchcommits.branch=branches.id)
                     JOIN commits ON (commits.id=branchcommits.commit)
                    WHERE branches.repository=%s
                      AND NOT branches.id=ANY (%s)
                      AND commits.sha1=%s""",
                (repository.id, exclude_branches, commit.sha1))

            base_branch_id, = cursor.fetchone()
            if base_branch_id is not None:
                tail = commit
                break

            commits.add(commit)
            stack.extend(reversed(commit.parents))

        if base_branch_id:
            commits = log.commitset.CommitSet.fromBranchUpdate(
                db, set(), tail, head)
            tail_id = tail.getId(db)
        else:
            tail_id = None

        return base_branch_id, tail_id, commits

    @staticmethod
    def insert(db, repository, user, branch_name, branch_type,
               base_id, head_id, tail_id, output, commits, pendingrefupdate_id):
        with db.updating_cursor("branches",
                                "branchupdates",
                                "branchcommits",
                                "branchupdatecommits",
                                "pendingrefupdates") as cursor:
            cursor.execute(
                """INSERT INTO branches (repository, name, type,
                                         base, head, tail)
                        VALUES (%s, %s, %s,
                                %s, %s, %s)
                     RETURNING id""",
                (repository.id, branch_name, branch_type,
                 base_id, head_id, tail_id))
            branch_id, = cursor.fetchone()

            cursor.execute(
                """INSERT INTO branchupdates (branch, updater,
                                              to_base, to_head, to_tail,
                                              output)
                        VALUES (%s, %s,
                                %s, %s, %s,
                                %s)
                     RETURNING id""",
                (branch_id, user.id,
                 base_id, head_id, tail_id,
                 output))
            branchupdate_id, = cursor.fetchone()

            cursor.executemany(
                """INSERT INTO branchcommits (branch, commit)
                        VALUES (%s, %s)""",
                ((branch_id, commit.getId(db))
                 for commit in commits))

            cursor.execute(
                """INSERT INTO branchupdatecommits
                                 (branchupdate, commit, associated)
                        SELECT %s, commit, TRUE
                          FROM branchcommits
                         WHERE branch=%s""",
                (branchupdate_id, branch_id))

            if pendingrefupdate_id is not None:
                cursor.execute(
                    """UPDATE pendingrefupdates
                          SET branchupdate=%s
                        WHERE id=%s""",
                    (branchupdate_id, pendingrefupdate_id))

        return branch_id

    @staticmethod
    def create(db, user, name, head, pendingrefupdate_id=None):
        import gitutils
        import textutils

        cursor = db.readonly_cursor()
        repository = head.repository

        base_id, tail_id, commits = Branch.findBaseBranch(db, head)

        if not user.isSystem():
            if base_id is not None:
                base_branch = Branch.fromId(db, base_id)
                output = textutils.reflow(
                    ("Branch created based on '%s', with %d associated "
                     "commits:")
                    % (base_branch.name, len(commits)),
                    line_length=80 - len("remote: "))
                for url_prefix in user.getCriticURLs(db):
                    output += ("\n  %s/log?repository=%s&branch=%s"
                               % (url_prefix, repository.name, name))
                if commits:
                    if len(commits) > 1:
                        output += ("\nTo create a review of all %d commits:"
                                   % len(commits))
                    else:
                        output += "\nTo create a review of the commit:"
                    for url_prefix in user.getCriticURLs(db):
                        output += ("\n  %s/createreview?repository=%s&branch=%s"
                                   % (url_prefix, repository.name, name))
            else:
                output = ("Branch created with %d associated commits."
                          % len(commits))
        else:
            output = None

        branch_id = Branch.insert(
            db, repository, user, name, 'normal', base_id, head.getId(db),
            tail_id, output, commits, pendingrefupdate_id)

        gitutils.emitGitHookOutput(db, pendingrefupdate_id, output)

        return Branch.fromId(db, branch_id)

    def update(self, db, user, from_commit, to_commit, flags,
               pendingrefupdate_id=None):
        import gitutils
        import log.commitset

        if self.head_sha1 != from_commit.sha1:
            raise InvalidUpdate(self.head_sha1, from_commit.sha1)

        commits = set(self.getCommits(db))
        base_id = self.base_id
        tail_id = self.tail_id

        if from_commit.isAncestorOf(to_commit):
            # Fast-forward update.
            is_rebase = False
            associated_commits = log.commitset.CommitSet.fromBranchUpdate(
                db, commits, from_commit, to_commit)
            disassociated_commits = []
        else:
            # Non-fast-forward update.
            is_rebase = True

            from dbutils.review import Review

            review = Review.fromBranch(db, self)
            if review:
                pending_rebase = review.getPendingRebase(db)

                # Things checked by the pre-receive hook, but that could
                # theoretically have changed independently now, although they
                # shouldn't be allowed to.
                assert pending_rebase
                assert pending_rebase.user == user

                if pending_rebase.old_upstream:
                    new_upstream = pending_rebase.new_upstream
                    if not new_upstream:
                        new_upstream = gitutils.Commit.fromSHA1(
                            db, self.repository, to_commit.parents[0])
                else:
                    commits = log.commitset.CommitSet(self.getCommits(db))
                    new_upstream = commits.findEquivalentUpstream(db, to_commit)

                new_commits = log.commitset.CommitSet.fromBranchUpdate(
                    db, set(), new_upstream, to_commit)
            else:
                mergebase_sha1 = self.repository.mergebase([from_commit,
                                                            to_commit])
                if mergebase_sha1 in commits:
                    mergebase = gitutils.Commit.fromSHA1(
                        db, self.repository, mergebase_sha1)
                    kept_commits = log.commitset.CommitSet(commits).getSubset(
                        mergebase)
                    added_commits = log.commitset.CommitSet.fromBranchUpdate(
                        db, kept_commits, mergebase, to_commit)
                    new_commits = log.commitset.CommitSet.union(
                        kept_commits, added_commits)
                else:
                    base_id, tail_id, new_commits = Branch.findBaseBranch(
                        db, to_commit, exclude_branches=[self.id])

            associated_commits = set(new_commits) - set(commits)
            disassociated_commits = set(commits) - set(new_commits)

        output = []
        if associated_commits:
            output.append("Associated %d new commit%s to the branch."
                          % (len(associated_commits),
                             "s" if len(associated_commits) > 1 else ""))
        if disassociated_commits:
            output.append("Disassociated %d old commit%s from the branch."
                          % (len(disassociated_commits),
                             "s" if len(disassociated_commits) > 1 else ""))
        output = "\n".join(output)

        with db.updating_cursor("branches",
                                "branchupdates",
                                "branchcommits",
                                "branchupdatecommits",
                                "pendingrefupdates") as cursor:
            cursor.execute(
                """INSERT INTO branchupdates (branch, updater,
                                              from_base, to_base,
                                              from_head, to_head,
                                              from_tail, to_tail,
                                              output)
                        VALUES (%s, %s,
                                %s, %s,
                                %s, %s,
                                %s, %s,
                                %s)
                     RETURNING id""",
                (self.id, user.id,
                 self.base_id, base_id,
                 from_commit.getId(db), to_commit.getId(db),
                 self.tail_id, tail_id,
                 output))

            (update_id,) = cursor.fetchone()

            # Update |branchcommits|.
            cursor.executemany(
                """INSERT
                     INTO branchcommits (branch, commit)
                   VALUES (%s, %s)""",
                ((self.id, commit.getId(db))
                 for commit in associated_commits))
            cursor.executemany(
                """DELETE
                     FROM branchcommits
                    WHERE branch=%s
                      AND commit=%s""",
                ((self.id, commit.getId(db))
                 for commit in disassociated_commits))

            # Record updates in |branchupdatecommits|.
            cursor.executemany(
                """INSERT
                     INTO branchupdatecommits (branchupdate, commit, associated)
                   VALUES (%s, %s, TRUE)""",
                ((update_id, commit.getId(db))
                 for commit in associated_commits))
            cursor.executemany(
                """INSERT
                     INTO branchupdatecommits (branchupdate, commit, associated)
                   VALUES (%s, %s, FALSE)""",
                ((update_id, commit.getId(db))
                 for commit in disassociated_commits))

            cursor.execute(
                """UPDATE branches
                      SET base=%s,
                          head=%s,
                          tail=%s
                    WHERE id=%s""",
                (base_id, to_commit.getId(db), tail_id, self.id))

            if pendingrefupdate_id is not None:
                cursor.execute(
                    """UPDATE pendingrefupdates
                          SET branchupdate=%s
                        WHERE id=%s""",
                    (update_id, pendingrefupdate_id))

        if output and not self.is_review_branch:
            gitutils.emitGitHookOutput(db, pendingrefupdate_id, output)

    def delete(self, db, user, commit, pendingrefupdate_id=None):
        if commit.sha1 != self.head_sha1:
            raise InvalidUpdate(self.head_commit_sha1, commit.sha1)

        with db.updating_cursor(
                "branches", "pendingrefupdateoutputs") as cursor:
            if pendingrefupdate_id:
                cursor.execute("""SELECT COUNT(*)
                                    FROM branchcommits
                                   WHERE branch=%s""",
                               (self.id,))
                commit_count, = cursor.fetchone()

            cursor.execute("""DELETE
                                FROM branches
                               WHERE id=%s""",
                           (self.id,))

            if pendingrefupdate_id is not None:
                output = ("Deleted branch with %d associated commits."
                          % commit_count)
                cursor.execute(
                    """INSERT INTO pendingrefupdateoutputs
                                     (pendingrefupdate, output)
                            VALUES (%s, %s)""",
                    (pendingrefupdate_id, output))

    @staticmethod
    def fromId(db, branch_id, load_review=False, repository=None, for_update=False, profiler=None):
        import gitutils

        cursor = db.cursor()
        cursor.execute("""SELECT name, repository, head, base, tail, branches.type, archived
                            FROM branches
                           WHERE branches.id=%s""",
                       (branch_id,),
                       for_update=for_update)
        row = cursor.fetchone()

        if not row: return None
        else:
            branch_name, repository_id, head_commit_id, base_branch_id, tail_commit_id, type, archived = row

            def commit_sha1(commit_id):
                cursor.execute("SELECT sha1 FROM commits WHERE id=%s", (commit_id,))
                return cursor.fetchone()[0]

            head_commit_sha1 = commit_sha1(head_commit_id)
            tail_commit_sha1 = (commit_sha1(tail_commit_id)
                                if tail_commit_id is not None else None)

            if profiler: profiler.check("Branch.fromId: basic")

            if repository is None:
                repository = gitutils.Repository.fromId(db, repository_id)

            assert repository.id == repository_id

            if profiler: profiler.check("Branch.fromId: repository")

            branch = Branch(branch_id, repository, branch_name, base_branch_id,
                            (head_commit_id, head_commit_sha1),
                            (tail_commit_id, tail_commit_sha1),
                            type, archived)

            if load_review:
                from dbutils import Review

                branch.review = Review.fromBranch(db, branch)

                if profiler: profiler.check("Branch.fromId: review")

            return branch

    @staticmethod
    def fromName(db, repository, name, **kwargs):
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT id
                            FROM branches
                           WHERE repository=%s
                             AND name=%s""",
                       (repository.id, name))
        row = cursor.fetchone()
        if not row:
            return None
        else:
            return Branch.fromId(db, row[0], repository=repository, **kwargs)
