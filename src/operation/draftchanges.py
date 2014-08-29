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
import profiling

from operation import Operation, OperationResult, Optional
from reviewing.comment import CommentChain, createCommentChain, createComment
from reviewing.mail import sendPendingMails
from reviewing.utils import generateMailsForBatch

class ReviewStateChange(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int })

    def process(self, db, user, review_id):
        cursor = db.cursor()

        def unaccepted():
            # Raised issues.
            cursor.execute("""SELECT 1
                                FROM commentchains
                               WHERE commentchains.review=%s
                                 AND commentchains.uid=%s
                                 AND commentchains.type='issue'
                                 AND commentchains.state='draft'""",
                           (review_id, user.id))
            if cursor.fetchone(): return True

            # Reopened issues.
            cursor.execute("""SELECT 1
                                FROM commentchainchanges
                                JOIN commentchains ON (commentchains.id=commentchainchanges.chain)
                               WHERE commentchains.review=%s
                                 AND commentchains.type='issue'
                                 AND commentchainchanges.uid=%s
                                 AND commentchainchanges.state='draft'
                                 AND commentchainchanges.from_state=commentchains.state
                                 AND commentchainchanges.to_state='open'
                                 AND commentchainchanges.to_type IS NULL""",
                           (review_id, user.id))
            if cursor.fetchone(): return True

            # Note converted into issues.
            cursor.execute("""SELECT 1
                                FROM commentchainchanges
                                JOIN commentchains ON (commentchains.id=commentchainchanges.chain)
                               WHERE commentchains.review=%s
                                 AND commentchains.type='note'
                                 AND commentchainchanges.uid=%s
                                 AND commentchainchanges.state='draft'
                                 AND commentchainchanges.from_type=commentchains.type
                                 AND commentchainchanges.to_type='issue'""",
                           (review_id, user.id))
            if cursor.fetchone(): return True

            # Unreviewed lines.
            cursor.execute("""SELECT 1
                                FROM reviewfilechanges
                                JOIN reviewfiles ON (reviewfiles.id=reviewfilechanges.file)
                               WHERE reviewfiles.review=%s
                                 AND reviewfilechanges.uid=%s
                                 AND reviewfilechanges.state='draft'
                                 AND reviewfilechanges.from=reviewfiles.state
                                 AND reviewfilechanges.to='pending'""",
                           (review_id, user.id))
            if cursor.fetchone(): return True

            # Otherwise still accepted (if accepted before.)
            return False

        def stillOpen():
            if unaccepted(): return True

            # Still open issues.
            cursor.execute("""SELECT 1
                                FROM commentchains
                     LEFT OUTER JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id
                                                         AND commentchainchanges.uid=%s
                                                         AND commentchainchanges.state='draft'
                                                         AND (commentchainchanges.to_state IN ('closed', 'addressed')
                                                           OR commentchainchanges.to_type='note'))
                               WHERE commentchains.review=%s
                                 AND commentchains.type='issue'
                                 AND commentchains.state='open'
                                 AND commentchainchanges.chain IS NULL""",
                           (user.id, review_id))
            if cursor.fetchone(): return True

            # Still pending lines.
            cursor.execute("""SELECT 1
                                FROM reviewfiles
                     LEFT OUTER JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id
                                                       AND reviewfilechanges.uid=%s
                                                       AND reviewfilechanges.state='draft'
                                                       AND reviewfilechanges.to='reviewed')
                               WHERE reviewfiles.review=%s
                                 AND reviewfiles.state='pending'
                                 AND reviewfilechanges.file IS NULL""",
                           (user.id, review_id))
            if cursor.fetchone(): return True

            # Otherwise accepted now.
            return False

        if dbutils.Review.isAccepted(db, review_id):
            return OperationResult(current_state="accepted", new_state="open" if unaccepted() else "accepted")
        else:
            return OperationResult(current_state="open", new_state="open" if stillOpen() else "accepted")

class SubmitChanges(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "remark": Optional(str) })

    def process(self, db, user, review_id, remark=None):
        cursor = db.cursor()
        profiler = profiling.Profiler()

        profiler.check("start")

        review = dbutils.Review.fromId(db, review_id, load_commits=False)

        profiler.check("create review")

        was_accepted = review.state == "open" and review.accepted(db)

        profiler.check("accepted before")

        if remark and remark.strip():
            chain_id = createCommentChain(db, user, review, 'note')
            createComment(db, user, chain_id, remark, first=True)
        else:
            chain_id = None

        # Create a batch that groups all submitted changes together.
        cursor.execute("INSERT INTO batches (review, uid, comment) VALUES (%s, %s, %s) RETURNING id", (review.id, user.id, chain_id))
        batch_id = cursor.fetchone()[0]

        profiler.check("batches++")

        # Reject all draft file approvals where the affected review file isn't in
        # the state it was in when the change was drafted.
        cursor.execute("""UPDATE reviewfilechanges
                             SET state='rejected',
                                 time=now()
                            FROM reviewfiles
                           WHERE reviewfiles.review=%s
                             AND reviewfiles.id=reviewfilechanges.file
                             AND reviewfilechanges.uid=%s
                             AND reviewfilechanges.state='draft'
                             AND reviewfilechanges.from!=reviewfiles.state""",
                       (review.id, user.id))

        profiler.check("reviewfilechanges reject state changes")

        # Then perform the remaining draft file approvals by updating the state of
        # the corresponding review file.
        cursor.execute("""UPDATE reviewfiles
                             SET state='reviewed',
                                 reviewer=reviewfilechanges.uid,
                                 time=now()
                            FROM reviewfilechanges
                           WHERE reviewfiles.review=%s
                             AND reviewfilechanges.uid=%s
                             AND reviewfilechanges.state='draft'
                             AND reviewfilechanges.file=reviewfiles.id
                             AND reviewfilechanges.from=reviewfiles.state
                             AND reviewfilechanges.to='reviewed'""",
                       (review.id, user.id))

        profiler.check("reviewfiles pending=>reviewed")

        # Then perform the remaining draft file disapprovals by updating the state
        # of the corresponding review file.
        cursor.execute("""UPDATE reviewfiles
                             SET state='pending',
                                 reviewer=NULL,
                                 time=now()
                            FROM reviewfilechanges
                           WHERE reviewfiles.review=%s
                             AND reviewfilechanges.uid=%s
                             AND reviewfilechanges.state='draft'
                             AND reviewfilechanges.file=reviewfiles.id
                             AND reviewfilechanges.from=reviewfiles.state
                             AND reviewfilechanges.to='pending'""",
                       (review.id, user.id))

        profiler.check("reviewfiles reviewed=>pending")

        # Finally change the state of just performed approvals from draft to
        # 'performed'.
        cursor.execute("""UPDATE reviewfilechanges
                             SET batch=%s,
                                 state='performed',
                                 time=now()
                            FROM reviewfiles
                           WHERE reviewfiles.review=%s
                             AND reviewfiles.id=reviewfilechanges.file
                             AND reviewfilechanges.uid=%s
                             AND reviewfilechanges.state='draft'
                             AND reviewfilechanges.to=reviewfiles.state""",
                       (batch_id, review.id, user.id))

        profiler.check("reviewfilechanges draft=>performed")

        # Find all chains with draft comments being submitted that the current user
        # isn't associated with via the commentchainusers table, and associate the
        # user with them.
        cursor.execute("""SELECT DISTINCT commentchains.id, commentchainusers.uid IS NULL
                            FROM commentchains
                            JOIN comments ON (comments.chain=commentchains.id)
                 LEFT OUTER JOIN commentchainusers ON (commentchainusers.chain=commentchains.id
                                                   AND commentchainusers.uid=comments.uid)
                           WHERE commentchains.review=%s
                             AND comments.uid=%s
                             AND comments.state='draft'""",
                       (review.id, user.id))

        for chain_id, need_associate in cursor.fetchall():
            if need_associate:
                cursor.execute("INSERT INTO commentchainusers (chain, uid) VALUES (%s, %s)", (chain_id, user.id))

        profiler.check("commentchainusers++")

        # Find all chains with draft comments being submitted and add a record for
        # every user associated with the chain to read the comment.
        cursor.execute("""INSERT
                            INTO commentstoread (uid, comment)
                          SELECT commentchainusers.uid, comments.id
                            FROM commentchains, commentchainusers, comments
                           WHERE commentchains.review=%s
                             AND commentchainusers.chain=commentchains.id
                             AND commentchainusers.uid!=comments.uid
                             AND comments.chain=commentchains.id
                             AND comments.uid=%s
                             AND comments.state='draft'""",
                       (review.id, user.id))

        profiler.check("commentstoread++")

        # Associate all users associated with a draft comment chain to
        # the review (if they weren't already.)
        cursor.execute("""SELECT DISTINCT commentchainusers.uid
                            FROM commentchains
                            JOIN commentchainusers ON (commentchainusers.chain=commentchains.id)
                 LEFT OUTER JOIN reviewusers ON (reviewusers.review=commentchains.review AND reviewusers.uid=commentchainusers.uid)
                           WHERE commentchains.review=%s
                             AND commentchains.uid=%s
                             AND commentchains.state='draft'
                             AND reviewusers.uid IS NULL""",
                       (review.id, user.id))

        for (user_id,) in cursor.fetchall():
            cursor.execute("INSERT INTO reviewusers (review, uid) VALUES (%s, %s)", (review.id, user_id))

        # Change state on all draft commentchains by the user in the review to 'open'.
        cursor.execute("""UPDATE commentchains
                             SET batch=%s,
                                 state='open',
                                 time=now()
                           WHERE commentchains.review=%s
                             AND commentchains.uid=%s
                             AND commentchains.state='draft'""",
                       (batch_id, review.id, user.id))

        profiler.check("commentchains draft=>open")

        # Reject all draft comment chain changes where the affected comment
        # chain isn't in the state it was in when the change was drafted, or has
        # been morphed into a note since the change was drafted.
        cursor.execute("""UPDATE commentchainchanges
                             SET state='rejected',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.from_state IS NOT NULL
                             AND (commentchainchanges.from_state!=commentchains.state
                               OR commentchainchanges.from_last_commit!=commentchains.last_commit
                               OR commentchains.type!='issue')""",
                       (review.id, user.id))

        profiler.check("commentchainchanges reject state changes")

        # Reject all draft comment chain changes where the affected comment chain
        # type isn't what it was in when the change was drafted.
        cursor.execute("""UPDATE commentchainchanges
                             SET state='rejected',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.from_type IS NOT NULL
                             AND commentchainchanges.from_type!=commentchains.type""",
                       (review.id, user.id))

        profiler.check("commentchainchanges reject type changes")

        # Reject all draft comment chain changes where the affected comment chain
        # addressed_by isn't what it was in when the change was drafted.
        cursor.execute("""UPDATE commentchainchanges
                             SET state='rejected',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.from_addressed_by IS NOT NULL
                             AND commentchainchanges.from_addressed_by!=commentchains.addressed_by""",
                       (review.id, user.id))

        profiler.check("commentchainchanges reject addressed_by changes")

        # Then perform the remaining draft comment chain changes by updating the
        # state of the corresponding comment chain.

        # Perform open->closed changes, including setting 'closed_by'.
        cursor.execute("""UPDATE commentchains
                             SET state='closed',
                                 closed_by=commentchainchanges.uid
                            FROM commentchainchanges
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.to_state='closed'""",
                       (review.id, user.id))

        profiler.check("commentchains closed")

        # Perform (closed|addressed)->open changes, including resetting 'closed_by' and
        # 'addressed_by' to NULL.
        cursor.execute("""UPDATE commentchains
                             SET state='open',
                                 last_commit=commentchainchanges.to_last_commit,
                                 closed_by=NULL,
                                 addressed_by=NULL
                            FROM commentchainchanges
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.to_state='open'""",
                       (review.id, user.id))

        profiler.check("commentchains reopen")

        # Perform addressed->addressed changes, i.e. updating 'addressed_by'.
        cursor.execute("""UPDATE commentchains
                             SET addressed_by=commentchainchanges.to_addressed_by
                            FROM commentchainchanges
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.to_addressed_by IS NOT NULL""",
                       (review.id, user.id))

        profiler.check("commentchains reopen (partial)")

        # Perform type changes.
        cursor.execute("""UPDATE commentchains
                             SET type=commentchainchanges.to_type
                            FROM commentchainchanges
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'
                             AND commentchainchanges.from_type=commentchains.type
                             AND commentchainchanges.to_type IS NOT NULL""",
                       (review.id, user.id))

        profiler.check("commentchains type change")

        # Finally change the state of just performed changes from draft to
        # 'performed'.
        cursor.execute("""UPDATE commentchainchanges
                             SET batch=%s,
                                 state='performed',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND commentchainchanges.chain=commentchains.id
                             AND commentchainchanges.uid=%s
                             AND commentchainchanges.state='draft'""",
                       (batch_id, review.id, user.id))

        profiler.check("commentchainchanges draft=>performed")

        # Change state on all draft commentchainlines by the user in the review to 'current'.
        cursor.execute("""UPDATE commentchainlines
                             SET state='current',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND commentchainlines.chain=commentchains.id
                             AND commentchainlines.uid=%s
                             AND commentchainlines.state='draft'""",
                       (review.id, user.id))

        profiler.check("commentchainlines draft=>current")

        # Change state on all draft comments by the user in the review to 'current'.
        cursor.execute("""UPDATE comments
                             SET batch=%s,
                                 state='current',
                                 time=now()
                            FROM commentchains
                           WHERE commentchains.review=%s
                             AND comments.chain=commentchains.id
                             AND comments.uid=%s
                             AND comments.state='draft'""",
                       (batch_id, review.id, user.id))

        profiler.check("comments draft=>current")

        # Associate the submitting user with the review if he isn't already.
        cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (review.id, user.id))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO reviewusers (review, uid) VALUES (%s, %s)", (review.id, user.id))

        generate_emails = profiler.start("generate emails")

        is_accepted = review.state == "open" and review.accepted(db)
        pending_mails = generateMailsForBatch(db, batch_id, was_accepted, is_accepted, profiler=profiler)

        generate_emails.stop()

        review.incrementSerial(db)
        db.commit()

        profiler.check("commit transaction")

        sendPendingMails(pending_mails)

        profiler.check("finished")

        if user.getPreference(db, "debug.profiling.submitChanges"):
            return OperationResult(batch_id=batch_id,
                                   serial=review.serial,
                                   profiling=profiler.output())
        else:
            return OperationResult(batch_id=batch_id,
                                   serial=review.serial)

class AbortChanges(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "what": { "approval": bool,
                                             "comments": bool,
                                             "metacomments": bool }})

    def process(self, db, user, review_id, what):
        cursor = db.cursor()
        profiler = profiling.Profiler()

        if what["approval"]:
            # Delete all pending review file approvals.
            cursor.execute("""DELETE
                                FROM reviewfilechanges
                               USING reviewfiles
                               WHERE reviewfiles.review=%s
                                 AND reviewfilechanges.file=reviewfiles.id
                                 AND reviewfilechanges.uid=%s
                                 AND reviewfilechanges.state='draft'""",
                           (review_id, user.id))
            profiler.check("approval")

        if what["comments"]:
            # Delete all pending comments chains.  This will, via ON DELETE CASCADE,
            # also delete all related comments and commentchainlines rows.
            cursor.execute("""DELETE
                                FROM commentchains
                               WHERE commentchains.review=%s
                                 AND commentchains.uid=%s
                                 AND commentchains.state='draft'""",
                           (review_id, user.id))
            profiler.check("chains")

            # Delete all still existing draft comments.
            cursor.execute("""DELETE
                                FROM comments
                               USING commentchains
                               WHERE commentchains.review=%s
                                 AND commentchains.id=comments.chain
                                 AND comments.uid=%s
                                 AND comments.state='draft'""",
                           (review_id, user.id))
            profiler.check("replies")

        if what["metacomments"]:
            # Delete all still existing draft comment lines.
            cursor.execute("""DELETE
                                FROM commentchainlines
                               USING commentchains
                               WHERE commentchains.review=%s
                                 AND commentchainlines.chain=commentchains.id
                                 AND commentchainlines.uid=%s
                                 AND commentchainlines.state='draft'
                                 AND commentchains.state!='draft'""",
                           (review_id, user.id))
            profiler.check("comment lines")

            # Delete all still existing draft comment state changes.
            cursor.execute("""DELETE
                                FROM commentchainchanges
                               USING commentchains
                               WHERE commentchains.review=%s
                                 AND commentchainchanges.chain=commentchains.id
                                 AND commentchainchanges.uid=%s
                                 AND commentchainchanges.state='draft'""",
                           (review_id, user.id))
            profiler.check("comment state")

        db.commit()

        if user.getPreference(db, "debug.profiling.abortChanges"):
            return OperationResult(profiling=profiler.output())
        else:
            return OperationResult()
