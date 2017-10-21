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

from operation import (Operation, OperationResult, OperationFailure, Optional,
                       NonNegativeInteger, PositiveInteger, Review, Commit, File)

from reviewing.comment import CommentChain, validateCommentChain, createCommentChain, createComment

class ValidateCommentChain(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review,
                                   "origin": {"old", "new"},
                                   "parent": Optional(Commit),
                                   "child": Commit,
                                   "file": File,
                                   "offset": PositiveInteger,
                                   "count": PositiveInteger })

    def process(self, db, user, review, origin, child, file, offset, count, parent=None):
        verdict, data = validateCommentChain(db, review, origin, parent, child, file, offset, count)
        return OperationResult(verdict=verdict, **data)

def checkComment(text):
    if not text.strip():
        raise OperationFailure(code="emptycomment",
                               title="Empty comment!",
                               message="Creating empty (or white-space only) comments is not allowed.")

class CreateCommentChain(Operation):
    def __init__(self):
        Operation.__init__(self, { "review": Review,
                                   "chain_type": {"issue", "note"},
                                   "commit_context": Optional({ "commit": Commit,
                                                                "offset": NonNegativeInteger,
                                                                "count": PositiveInteger }),
                                   "file_context": Optional({ "origin": {"old", "new"},
                                                              "parent": Optional(Commit),
                                                              "child": Commit,
                                                              "file": File,
                                                              "offset": PositiveInteger,
                                                              "count": PositiveInteger }),
                                   "text": str })

    def process(self, db, user, review, chain_type, text, commit_context=None, file_context=None):
        checkComment(text)

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
        checkComment(text)

        chain = CommentChain.fromId(db, chain_id, user)
        comment_id = createComment(db, user, chain_id, text)

        db.commit()

        return OperationResult(comment_id=comment_id, draft_status=chain.review.getDraftStatus(db, user))
