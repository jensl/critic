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

from operation import Operation, OperationResult, OperationError, Optional
from review.comment import Comment, CommentChain

class SetCommentChainState(Operation):
    def __init__(self, parameters):
        Operation.__init__(self, parameters)

    def setChainState(self, db, user, chain, old_state, new_state, new_last_commit=None):
        review = chain.review

        if chain.state != old_state:
            raise OperationError, "the comment chain's state is not '%s'" % old_state
        if new_state == "open" and review.state != "open":
            raise OperationError, "can't reopen comment chain in %s review" % review.state

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

        return OperationResult(draft_status=review.getDraftStatus(db, user))

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

        if not existing:
            cursor = db.cursor()
            cursor.execute("""INSERT INTO commentchainlines (chain, uid, commit, sha1, first_line, last_line)
                              VALUES (%s, %s, %s, %s, %s, %s)""",
                           (chain.id, user.id, commit_id, sha1, offset, offset + count - 1))
        elif offset != existing[0] or count != existing[1]:
            raise OperationError, "the comment chain is already present at other lines in same file version"

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

        if new_type == "issue": old_type = "note"
        else: old_type = "issue"

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
        Operation.__init__(self, { "chain_ids": [int] })

    def process(self, db, user, chain_ids):
        cursor = db.cursor()
        cursor.execute("""DELETE FROM commentstoread
                                USING comments
                                WHERE commentstoread.uid=%s
                                  AND commentstoread.comment=comments.id
                                  AND comments.chain=ANY (%s)""",
                       (user.id, chain_ids))

        db.commit()

        return OperationResult()
