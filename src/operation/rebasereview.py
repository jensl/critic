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

from operation import (Operation, OperationResult, OperationError, Optional,
                       Review)

def doPrepareRebase(db, user, review, new_upstream_arg=None, branch=None):
    commitset = log.commitset.CommitSet(review.branch.getCommits(db))
    tails = commitset.getFilteredTails(review.branch.repository)

    cursor = db.cursor()

    cursor.execute("SELECT uid FROM reviewrebases WHERE review=%s AND branchupdate IS NULL", (review.id,))
    row = cursor.fetchone()
    if row:
        rebaser = dbutils.User.fromId(db, row[0])
        raise OperationError("The review is already being rebased by %s <%s>." % (rebaser.fullname, rebaser.email))

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

    with db.updating_cursor("reviews",
                            "reviewrebases",
                            "previousbranchcommits") as cursor:
        cursor.execute(
            """INSERT INTO reviewrebases (review, old_upstream, new_upstream,
                                          uid, branch)
                    VALUES (%s, %s, %s, %s, %s)
                 RETURNING id""",
            (review.id, old_upstream_id, new_upstream_id, user.id, branch))

        rebase_id, = cursor.fetchone()

        review.incrementSerial(db)

    return rebase_id

def doCancelRebase(db, user, review):
    with db.updating_cursor("reviews",
                            "reviewrebases") as cursor:
        cursor.execute(
            """DELETE
                 FROM reviewrebases
                WHERE review=%s
                  AND branchupdate IS NULL""",
            (review.id,))

        review.incrementSerial(db)

class CheckRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        tails = review.getFilteredTails(db)
        available = "both" if len(tails) == 1 else "inplace"

        return OperationResult(available=available)

class SuggestUpstreams(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        review = dbutils.Review.fromId(db, review_id)
        tails = review.getFilteredTails(db)

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
        Operation.__init__(self, { "review": Review,
                                   "new_upstream": Optional(str),
                                   "branch": Optional(str) })

    def process(self, db, user, review, new_upstream=None, branch=None):
        rebase_id = doPrepareRebase(db, user, review, new_upstream, branch)
        return OperationResult(rebase_id=rebase_id)

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

        with db.updating_cursor("reviews", "trackedbranches") as cursor:
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

        commitset = log.commitset.CommitSet(review.branch.getCommits(db))
        tails = commitset.getFilteredTails(review.branch.repository)

        if len(tails) == 1 and tails.pop() == new_upstream_sha1:
            # This appears to be a history rewrite.
            new_upstream_sha1 = None

        try:
            doPrepareRebase(db, user, review, new_upstream_sha1, branch)

            try:
                with review.repository.relaycopy("RebaseReview") as relay:
                    with review.repository.temporaryref(new_head) as ref_name:
                        relay.run("fetch", "origin", ref_name)
                    relay.run("push", "--force", "origin",
                              "%s:refs/heads/%s" % (new_head.sha1, review.branch.name),
                              env={ "REMOTE_USER": user.name })
            except:
                doCancelRebase(db, user, review)
                raise
        finally:
            db.refresh()

            with db.updating_cursor("reviews", "trackedbranches") as cursor:
                if closed_by is not None:
                    state = review.getReviewState(db)
                    if state.accepted:
                        review.serial += 1
                        cursor.execute("UPDATE reviews SET state='closed', serial=%s, closed_by=%s WHERE id=%s", (review.serial, closed_by, review.id))

                if trackedbranch and not trackedbranch.disabled:
                    cursor.execute("UPDATE trackedbranches SET disabled=FALSE WHERE id=%s", (trackedbranch.id,))
                if new_trackedbranch:
                    cursor.execute("UPDATE trackedbranches SET remote_name=%s WHERE id=%s", (new_trackedbranch, trackedbranch.id))

        return OperationResult()

class RevertRebase(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review,
                                   "rebase_id": int })

    def process(self, db, user, review, rebase_id):
        cursor = db.cursor()

        cursor.execute(
            """SELECT branchupdate, to_head, equivalent_merge, replayed_rebase
                 FROM reviewrebases
                 JOIN branchupdates ON (reviewrebases.branchupdate=branchupdates.id)
                WHERE reviewrebases.id=%s""",
            (rebase_id,))
        (branchupdate_id, new_head_id,
         equivalent_merge_id, replayed_rebase_id) = cursor.fetchone()

        if review.branch.head_id != new_head_id:
            raise OperationError("Rebase cannot be reverted; "
                                 "additional commits have been pushed.")

        with db.updating_cursor("commentchains",
                                "branches",
                                "branchupdates",
                                "branchcommits") as cursor:
            # Reopen any issues marked as addressed by the rebase.  If the
            # rebase was a fast-forward one, issues will have been addressed by
            # the equivalent merge commit.  Otherwise, issues will have been
            # addressed by the new head commit (not the replayed rebase commit.)
            cursor.execute("""UPDATE commentchains
                                 SET state='open',
                                     addressed_by=NULL,
                                     addressed_by_update=NULL
                               WHERE review=%s
                                 AND state='addressed'
                                 AND addressed_by_update=%s""",
                           (review.id, branchupdate_id))

            # Revert the branch update's effect on the branch and delete it from
            # the |branchupdates| table.  Deleting it will through cascading
            # also delete rows from |reviewrebases| and |reviewchangesets|.
            dbutils.Branch.revertUpdate(
                db, branchupdate_id, reverting_rebase=True)

        review.invalidateCaches(db)

        return OperationResult()
