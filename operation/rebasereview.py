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

import dbutils
import gitutils
import log.commitset

from operation import Operation, OperationResult, OperationError, Optional

def doPrepareRebase(db, user, review, new_upstream_arg=None, branch=None):
    commitset = log.commitset.CommitSet(review.branch.commits)
    tails = commitset.getFilteredTails(review.branch.repository)

    cursor = db.cursor()

    cursor.execute("SELECT uid FROM reviewrebases WHERE review=%s AND new_head IS NULL", (review.id,))
    row = cursor.fetchone()
    if row:
        rebaser = dbutils.User.fromId(db, row[0])
        raise OperationError("The review is already being rebased by %s <%s>." % (rebaser.fullname, rebaser.email))

    head = commitset.getHeads().pop()
    head_id = head.getId(db)

    if new_upstream_arg is not None:
        if len(tails) > 1:
            raise OperationError("Rebase to new upstream commit not supported.")

        tail = gitutils.Commit.fromSHA1(db, review.branch.repository, tails.pop())

        old_upstream_id = tail.getId(db)
        if new_upstream_arg == "0" * 40:
            new_upstream_id = None
        else:
            if not gitutils.re_sha1.match(new_upstream_arg):
                cursor.execute("SELECT sha1 FROM tags WHERE repository=%s AND name=%s", (review.branch.repository.id, new_upstream_arg))
                row = cursor.fetchone()
                if row: new_upstream_arg = row[0]
                else: raise OperationError("Specified new upstream is invalid.")

            try: new_upstream = gitutils.Commit.fromSHA1(db, review.branch.repository, new_upstream_arg)
            except: raise OperationError("The specified new upstream commit does not exist in Critic's repository.")

            new_upstream_id = new_upstream.getId(db)
    else:
        old_upstream_id = None
        new_upstream_id = None

    cursor.execute("""INSERT INTO reviewrebases (review, old_head, new_head, old_upstream, new_upstream, uid, branch)
                           VALUES (%s, %s, NULL, %s, %s, %s, %s)""",
                   (review.id, head_id, old_upstream_id, new_upstream_id, user.id, branch))

    review.incrementSerial(db)

    db.commit()

def doCancelRebase(db, user, review):
    review.incrementSerial(db)

    db.cursor().execute("DELETE FROM reviewrebases WHERE review=%s AND new_head IS NULL", (review.id,))
    db.commit()

class CheckRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        tails = review.getFilteredTails()
        available = "both" if len(tails) == 1 else "inplace"

        return OperationResult(available=available)

class SuggestUpstreams(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        tails = review.getFilteredTails()

        if len(tails) > 1:
            raise OperationError("Multiple tail commits.")

        try:
            from customization.filtertags import getUpstreamPattern
        except ImportError:
            def getUpstreamTagPattern(review): pass

        tail = tails.pop()
        tags = review.branch.repository.run("tag", "-l", "--contains", tail, getUpstreamTagPattern(review) or "*").splitlines()

        cursor = db.cursor()
        upstreams = []

        for tag in tags:
            cursor.execute("SELECT sha1 FROM tags WHERE repository=%s AND name=%s", (review.branch.repository.id, tag))
            row = cursor.fetchone()
            if row and row[0] != tail:
                upstreams.append(tag)

        return OperationResult(upstreams=upstreams)

class PrepareRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "new_upstream": Optional(str),
                                   "branch": Optional(str) })

    def process(self, db, user, review_id, new_upstream=None, branch=None):
        review = dbutils.Review.fromId(db, review_id)
        doPrepareRebase(db, user, review, new_upstream, branch)
        return OperationResult()

class CancelRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        doCancelRebase(db, user, review)
        return OperationResult()

class RebaseReview(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "new_head_sha1": str,
                                   "new_upstream_sha1": Optional(str),
                                   "branch": Optional(str),
                                   "new_trackedbranch": Optional(str) })

    def process(self, db, user, review_id, new_head_sha1, new_upstream_sha1=None, branch=None, new_trackedbranch=None):
        review = dbutils.Review.fromId(db, review_id)
        new_head = gitutils.Commit.fromSHA1(db, review.repository, new_head_sha1)

        cursor = db.cursor()

        if review.state == 'closed':
            cursor.execute("SELECT closed_by FROM reviews WHERE id=%s", (review.id,))
            closed_by = cursor.fetchone()[0]

            review.serial += 1
            cursor.execute("UPDATE reviews SET state='open', serial=%s, closed_by=NULL WHERE id=%s", (review.serial, review.id))
        else:
            closed_by = None

        trackedbranch = review.getTrackedBranch(db)
        if trackedbranch and not trackedbranch.disabled:
            cursor.execute("UPDATE trackedbranches SET disabled=TRUE WHERE id=%s", (trackedbranch.id,))

        commitset = log.commitset.CommitSet(review.branch.commits)
        tails = commitset.getFilteredTails(review.branch.repository)

        if len(tails) == 1 and tails.pop() == new_upstream_sha1:
            # This appears to be a history rewrite.
            new_upstream_sha1 = None

        doPrepareRebase(db, user, review, new_upstream_sha1, branch)

        try:
            review.repository.run("update-ref", "refs/commit/%s" % new_head.sha1, new_head.sha1)

            with review.repository.relaycopy("RebaseReview") as relay:
                relay.run("fetch", "origin", "refs/commit/%s" % new_head.sha1)
                relay.run("push", "-f", "origin", "%s:refs/heads/%s" % (new_head.sha1, review.branch.name))

            if closed_by is not None:
                db.commit()
                state = review.getReviewState(db)
                if state.accepted:
                    review.serial += 1
                    cursor.execute("UPDATE reviews SET state='closed', serial=%s, closed_by=%s WHERE id=%s", (review.serial, closed_by, review.id))

            if trackedbranch and not trackedbranch.disabled:
                cursor.execute("UPDATE trackedbranches SET disabled=FALSE WHERE id=%s", (trackedbranch.id,))
            if new_trackedbranch:
                cursor.execute("UPDATE trackedbranches SET remote_name=%s WHERE id=%s", (new_trackedbranch, trackedbranch.id))

            db.commit()
        except:
            doCancelRebase(db, user, review)
            raise

        return OperationResult()

class RevertRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "rebase_id": int })

    def process(self, db, user, review_id, rebase_id):
        review = dbutils.Review.fromId(db, review_id)

        cursor = db.cursor()

        cursor.execute("SELECT old_head, new_head, new_upstream FROM reviewrebases WHERE id=%s", (rebase_id,))
        old_head_id, new_head_id, new_upstream_id = cursor.fetchone()

        cursor.execute("SELECT commit FROM previousreachable WHERE rebase=%s", (rebase_id,))
        reachable = [commit_id for (commit_id,) in cursor]

        if not reachable:
            # Fail if rebase was done before the 'previousreachable' table was
            # added, and we thus don't know what commits the branch contained
            # before the rebase.
            raise OperationError("Automatic revert not supported; rebase is pre-historic.")

        if review.branch.head.getId(db) != new_head_id:
            raise OperationError("Commits added to review after rebase; need to remove them first.")

        old_head = gitutils.Commit.fromId(db, review.repository, old_head_id)
        new_head = gitutils.Commit.fromId(db, review.repository, new_head_id)

        cursor.execute("DELETE FROM reachable WHERE branch=%s", (review.branch.id,))
        cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", [(review.branch.id, commit_id) for commit_id in reachable])

        if new_upstream_id:
            new_upstream = gitutils.Commit.fromId(db, review.repository, new_upstream_id)

            if len(old_head.parents) == 2 and old_head.parents[1] == new_upstream.sha1:
                # Equivalent merge commit was added; remove it too.

                # Reopen any issues marked as addressed by the merge commit.
                cursor.execute("""UPDATE commentchains
                                     SET state='open', addressed_by=NULL
                                   WHERE review=%s
                                     AND state='addressed'
                                     AND addressed_by=%s""",
                               (review.id, old_head_id))

                # Delete the review changesets (and, via cascade, all related
                # assignments.)
                cursor.execute("""DELETE FROM reviewchangesets
                                        USING changesets
                                        WHERE reviewchangesets.review=%s
                                          AND reviewchangesets.changeset=changesets.id
                                          AND changesets.child=%s""",
                               (review.id, old_head_id))

                old_head = gitutils.Commit.fromSHA1(db, review.repository, old_head.parents[0])
                old_head_id = old_head.getId(db)
            else:
                # Delete the review changesets (and, via cascade, all related
                # assignments.)
                cursor.execute("""DELETE FROM reviewchangesets
                                        USING changesets
                                        WHERE reviewchangesets.review=%s
                                          AND reviewchangesets.changeset=changesets.id
                                          AND changesets.child=%s
                                          AND changesets.type='conflicts'""",
                               (review.id, new_head_id))

        cursor.execute("UPDATE branches SET head=%s WHERE id=%s", (old_head_id, review.branch.id))
        cursor.execute("DELETE FROM reviewrebases WHERE id=%s", (rebase_id,))

        db.commit()

        review.repository.run("update-ref", "refs/heads/%s" % review.branch.name, old_head.sha1, new_head.sha1)

        return OperationResult()
