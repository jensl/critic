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

from operation import Operation, OperationResult, OperationError, OperationFailure, Optional
from reviewing.comment import Comment, CommentChain, propagate

class SetCommentChainState(Operation):
    def __init__(self, parameters):
        Operation.__init__(self, parameters)

    def setChainState(self, db, user, chain, old_state, new_state, new_last_commit=None):
        review = chain.review

        if chain.state != old_state:
            raise OperationFailure(code="invalidoperation",
                                   title="Invalid operation",
                                   message="The comment chain's state is not '%s'; can't change state to '%s'." % (old_state, new_state))
        elif new_state == "open" and review.state != "open":
            raise OperationFailure(code="invalidoperation",
                                   title="Invalid operation",
                                   message="Can't reopen comment chain in %s review!" % review.state)

        if chain.last_commit:
            old_last_commit = chain.last_commit.id
            if new_last_commit is None:
                new_last_commit = old_last_commit
        else:
            old_last_commit = new_last_commit = None

        cursor = db.cursor()

        if chain.state_is_draft:
            # The user is reverting a draft state change; just undo the draft
            # change.
            cursor.execute("""DELETE FROM commentchainchanges
                               WHERE chain=%s
                                 AND uid=%s
                                 AND to_state IS NOT NULL""",
                           (chain.id, user.id))

        else:
            # Otherwise insert a new row into the commentchainchanges table.
            cursor.execute("""INSERT INTO commentchainchanges (review, uid, chain, from_state, to_state, from_last_commit, to_last_commit)
                              VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                           (review.id, user.id, chain.id, old_state, new_state, old_last_commit, new_last_commit))

        db.commit()

        return OperationResult(old_state=old_state, new_state=new_state,
                               draft_status=review.getDraftStatus(db, user))

class ReopenResolvedCommentChain(SetCommentChainState):
    def __init__(self):
        SetCommentChainState.__init__(self, { "chain_id": int })

    def process(self, db, user, chain_id):
        return self.setChainState(db, user, CommentChain.fromId(db, chain_id, user), "closed", "open")

class ReopenAddressedCommentChain(SetCommentChainState):
    def __init__(self):
        SetCommentChainState.__init__(self, { "chain_id": int,
                                              "commit_id": int,
                                              "sha1": str,
                                              "offset": int,
                                              "count": int })

    def process(self, db, user, chain_id, commit_id, sha1, offset, count):
        chain = CommentChain.fromId(db, chain_id, user)
        existing = chain.lines_by_sha1.get(sha1)

        if chain.state != "addressed":
            raise OperationFailure(code="invalidoperation",
                                   title="Invalid operation",
                                   message="The comment chain is not marked as addressed!")

        if not existing:
            assert commit_id == chain.addressed_by.getId(db)

            commits = chain.review.getCommitSet(db).without(chain.addressed_by.parents)

            propagation = propagate.Propagation(db)
            propagation.setExisting(chain.review, chain.id, chain.addressed_by, chain.file_id, offset, offset + count - 1, True)
            propagation.calculateAdditionalLines(commits)

            commentchainlines_values = []

            for file_sha1, (first_line, last_line) in propagation.new_lines.items():
                commentchainlines_values.append((chain.id, user.id, file_sha1, first_line, last_line))

            cursor = db.cursor()
            cursor.executemany("""INSERT INTO commentchainlines (chain, uid, sha1, first_line, last_line)
                                  VALUES (%s, %s, %s, %s, %s)""",
                               commentchainlines_values)

            if not propagation.active:
                old_addressed_by_id = chain.addressed_by.getId(db)
                new_addressed_by_id = propagation.addressed_by[0].child.getId(db)

                if chain.addressed_by_is_draft:
                    cursor.execute("""UPDATE commentchainchanges
                                         SET to_addressed_by=%s
                                       WHERE chain=%s
                                         AND uid=%s
                                         AND state='draft'
                                         AND to_addressed_by=%s""",
                                   (new_addressed_by_id, chain.id, user.id, old_addressed_by_id))
                else:
                    cursor.execute("""INSERT INTO commentchainchanges (review, uid, chain, from_addressed_by, to_addressed_by)
                                      VALUES (%s, %s, %s, %s, %s)""",
                                   (chain.review.id, user.id, chain.id, old_addressed_by_id, new_addressed_by_id))

                old_last_commit_id = chain.last_commit.getId(db)
                new_last_commit_id = chain.addressed_by.getId(db)

                if chain.last_commit_is_draft:
                    cursor.execute("""UPDATE commentchainchanges
                                         SET to_last_commit=%s
                                       WHERE chain=%s
                                         AND uid=%s
                                         AND state='draft'
                                         AND to_last_commit=%s""",
                                   (new_last_commit_id, chain.id, user.id, old_last_commit_id))
                else:
                    cursor.execute("""INSERT INTO commentchainchanges (review, uid, chain, from_last_commit, to_last_commit)
                                      VALUES (%s, %s, %s, %s, %s)""",
                                   (chain.review.id, user.id, chain.id, old_last_commit_id, new_last_commit_id))

                db.commit()

                return OperationResult(old_state='addressed', new_state='addressed',
                                       draft_status=chain.review.getDraftStatus(db, user))
        elif offset != existing[0] or count != existing[1]:
            raise OperationFailure(code="invalidoperation",
                                   title="Invalid operation",
                                   message="The comment chain is already present at other lines in same file version")

        return self.setChainState(db, user, chain, "addressed", "open", new_last_commit=commit_id)

class ResolveCommentChain(SetCommentChainState):
    def __init__(self):
        Operation.__init__(self, { "chain_id": int })

    def process(self, db, user, chain_id):
        return self.setChainState(db, user, CommentChain.fromId(db, chain_id, user), "open", "closed")

class MorphCommentChain(Operation):
    def __init__(self):
        Operation.__init__(self, { "chain_id": int,
                                   "new_type": set(["issue", "note"]) })

    def process(self, db, user, chain_id, new_type):
        chain = CommentChain.fromId(db, chain_id, user)
        review = chain.review

        if chain.type == new_type:
            raise OperationError, "the comment chain's type is already '%s'" % new_type
        elif new_type == "note" and chain.state in ("closed", "addressed"):
            raise OperationError, "can't convert resolved or addressed issue to a note"

        cursor = db.cursor()

        if chain.state == "draft":
            # The chain is still a draft; just change its type directly.
            cursor.execute("""UPDATE commentchains
                                 SET type=%s
                               WHERE id=%s""",
                           (new_type, chain.id))

        elif chain.type_is_draft:
            # The user is reverting a draft chain type change; just undo the
            # draft change.
            cursor.execute("""DELETE FROM commentchainchanges
                               WHERE chain=%s
                                 AND uid=%s
                                 AND to_type IS NOT NULL""",
                           (chain.id, user.id))

        else:
            # Otherwise insert a new row into the commentchainchanges table.
            cursor.execute("""INSERT INTO commentchainchanges (review, uid, chain, from_type, to_type)
                              VALUES (%s, %s, %s, %s, %s)""",
                           (review.id, user.id, chain.id, chain.type, new_type))

        db.commit()

        return OperationResult(draft_status=review.getDraftStatus(db, user))

class UpdateComment(Operation):
    def __init__(self):
        Operation.__init__(self, { "comment_id": int,
                                   "new_text": str })

    def process(self, db, user, comment_id, new_text):
        comment = Comment.fromId(db, comment_id, user)

        if user != comment.user:
            raise OperationError, "can't edit comment written by another user"
        if comment.state != "draft":
            raise OperationError, "can't edit comment that has been submitted"
        if not new_text.strip():
            raise OperationError, "empty comment"

        cursor = db.cursor()
        cursor.execute("""UPDATE comments
                             SET comment=%s, time=now()
                           WHERE id=%s""",
                       (new_text, comment.id))

        db.commit()

        return OperationResult(draft_status=comment.chain.review.getDraftStatus(db, user))

class DeleteComment(Operation):
    def __init__(self):
        Operation.__init__(self, { "comment_id": int })

    def process(self, db, user, comment_id):
        comment = Comment.fromId(db, comment_id, user)

        if user != comment.user:
            raise OperationError, "can't delete comment written by another user"
        if comment.state != "draft":
            raise OperationError, "can't delete comment that has been submitted"

        cursor = db.cursor()
        cursor.execute("""UPDATE comments
                             SET state='deleted'
                           WHERE id=%s""",
                       (comment.id,))

        if comment.chain.state == "draft":
            # If the comment chain was a draft, then delete it as well.
            cursor.execute("""UPDATE commentchains
                                 SET state='empty'
                               WHERE id=%s""",
                           (comment.chain.id,))

        db.commit()

        return OperationResult(draft_status=comment.chain.review.getDraftStatus(db, user))

class MarkChainsAsRead(Operation):
    def __init__(self):
        Operation.__init__(self, { "chain_ids": Optional([int]),
                                   "review_ids": Optional([int]) })

    def process(self, db, user, chain_ids=None, review_ids=None):
        cursor = db.cursor()

        if chain_ids:
            cursor.execute("""DELETE FROM commentstoread
                                    USING comments
                                    WHERE commentstoread.uid=%s
                                      AND commentstoread.comment=comments.id
                                      AND comments.chain=ANY (%s)""",
                           (user.id, chain_ids))

        if review_ids:
            cursor.execute("""DELETE FROM commentstoread
                                    USING comments, commentchains
                                    WHERE commentstoread.uid=%s
                                      AND commentstoread.comment=comments.id
                                      AND comments.chain=commentchains.id
                                      AND commentchains.review=ANY (%s)""",
                           (user.id, review_ids))

        db.commit()

        return OperationResult()
