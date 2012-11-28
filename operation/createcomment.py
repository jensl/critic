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

from operation import Operation, OperationResult, Optional
from reviewing.comment import CommentChain, validateCommentChain, createCommentChain, createComment

class ValidateCommentChain(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "file_id": int,
                                   "sha1": str,
                                   "offset": int,
                                   "count": int })

    def process(self, db, user, review_id, file_id, sha1, offset, count):
        review = dbutils.Review.fromId(db, review_id)
        verdict, data = validateCommentChain(db, review, file_id, sha1, offset, count)
        return OperationResult(verdict=verdict, **data)

class CreateCommentChain(Operation):
    def __init__(self):
        Operation.__init__(self, { "review_id": int,
                                   "chain_type": set(["issue", "note"]),
                                   "commit_context": Optional({ "commit_id": int,
                                                                "offset": int,
                                                                "count": int }),
                                   "file_context": Optional({ "origin": set(["old", "new"]),
                                                              "parent_id": Optional(int),
                                                              "child_id": int,
                                                              "file_id": int,
                                                              "old_sha1": Optional(str),
                                                              "new_sha1": Optional(str),
                                                              "offset": int,
                                                              "count": int }),
                                   "text": str })

    def process(self, db, user, review_id, chain_type, text, commit_context=None, file_context=None):
        review = dbutils.Review.fromId(db, review_id)

        if commit_context:
            chain_id = createCommentChain(db, user, review, chain_type, **commit_context)
        elif file_context:
            chain_id = createCommentChain(db, user, review, chain_type, **file_context)
        else:
            chain_id = createCommentChain(db, user, review, chain_type)

        comment_id = createComment(db, user, chain_id, text, first=True)

        db.commit()

        return OperationResult(chain_id=chain_id, comment_id=comment_id, draft_status=review.getDraftStatus(db, user))

class CreateComment(Operation):
    def __init__(self):
        Operation.__init__(self, { "chain_id": int,
                                   "text": str })

    def process(self, db, user, chain_id, text):
        chain = CommentChain.fromId(db, chain_id, user)
        comment_id = createComment(db, user, chain_id, text)

        db.commit()

        return OperationResult(comment_id=comment_id, draft_status=chain.review.getDraftStatus(db, user))
