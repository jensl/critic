# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import api
from . import apiobject

class ModifiedComment(object):
    def __init__(self, comment_id, new_type, new_state):
        self.id = comment_id
        self.new_type = new_type
        self.new_state = new_state

class Batch(apiobject.APIObject):
    wrapper_class = api.batch.Batch

    def __init__(self, batch_id, review_id, author_id, comment_id, timestamp):
        self.id = batch_id
        self.__review_id = review_id
        self.__author_id = author_id
        self.__comment_id = comment_id
        self.timestamp = timestamp
        self.__created_comment_ids = None
        self.__written_reply_ids = None
        self.__modified_comments = None
        self.__reviewed_file_changes = None
        self.__unreviewed_file_changes = None

    def isEmpty(self, critic):
        self.loadCommentChanges(critic)
        self.loadFileChanges(critic)
        return not (self.__created_comment_ids or
                    self.__written_reply_ids or
                    self.__modified_comments or
                    self.__reviewed_file_changes or
                    self.__unreviewed_file_changes)

    def getReview(self, critic):
        return api.review.fetch(critic, self.__review_id)

    def getAuthor(self, critic):
        if self.__author_id is None:
            return None
        return api.user.fetch(critic, self.__author_id)

    def getComment(self, critic):
        if self.__comment_id is None:
            return None
        return api.comment.fetch(critic, self.__comment_id)

    def getCreatedComments(self, critic):
        if self.__created_comment_ids is None:
            self.loadCommentChanges(critic)
        return set(api.comment.fetchMany(critic, self.__created_comment_ids))

    def getWrittenReplies(self, critic):
        if self.__written_reply_ids is None:
            self.loadCommentChanges(critic)
        return set(api.reply.fetchMany(critic, self.__written_reply_ids))

    def getResolvedIssues(self, critic):
        if self.__modified_comments is None:
            self.loadCommentChanges(critic)
        return set(api.comment.fetchMany(
            critic, (modified_comment.id
                     for modified_comment in self.__modified_comments
                     if modified_comment.new_state == "closed")))

    def getReopenedIssues(self, critic):
        if self.__modified_comments is None:
            self.loadCommentChanges(critic)
        return set(api.comment.fetchMany(
            critic, (modified_comment.id
                     for modified_comment in self.__modified_comments
                     if modified_comment.new_state == "open")))

    def getMorphedComments(self, critic):
        if self.__modified_comments is None:
            self.loadCommentChanges(critic)
        new_type_by_comment_id = {
            modified_comment.id: modified_comment.new_type
            for modified_comment in self.__modified_comments
            if modified_comment.new_type is not None
        }
        comments = api.comment.fetchMany(critic, new_type_by_comment_id.keys())
        return {
            comment: new_type_by_comment_id[comment.id]
            for comment in comments
        }

    def getReviewedFileChanges(self, critic):
        if self.__reviewed_file_changes is None:
            self.loadFileChanges(critic)
        return api.reviewablefilechange.fetchMany(
            critic, self.__reviewed_file_changes)

    def getUnreviewedFileChanges(self, critic):
        if self.__reviewed_file_changes is None:
            self.loadFileChanges(critic)
        return api.reviewablefilechange.fetchMany(
            critic, self.__unreviewed_file_changes)

    def __queryCondition(self):
        if self.id is None:
            condition = "state='draft'"
            batch_id = ()
        else:
            condition = "batch=%s"
            batch_id = (self.id,)
        return condition, batch_id

    def loadCommentChanges(self, critic):
        cursor = critic.getDatabaseCursor()
        condition, batch_id = self.__queryCondition()
        cursor.execute("""SELECT commentchains.id, comments.id,
                                 commentchains.first_comment=comments.id
                            FROM commentchains
                            JOIN comments ON (comments.chain=commentchains.id)
                           WHERE commentchains.review=%s
                             AND commentchains.state!='empty'
                             AND comments.uid=%s
                             AND comments.state!='deleted'
                             AND comments.{}""".format(condition),
                       (self.__review_id, self.__author_id) + batch_id)
        self.__created_comment_ids = []
        self.__written_reply_ids = []
        for comment_id, reply_id, is_initial in cursor:
            # Don't include the note that is the batch's comment.
            if comment_id == self.__comment_id:
                continue
            if is_initial:
                self.__created_comment_ids.append(comment_id)
            else:
                self.__written_reply_ids.append(reply_id)
        cursor.execute(
            """SELECT commentchains.id, to_type, to_state
                 FROM commentchains
                 JOIN commentchainchanges
                      ON (commentchainchanges.chain=commentchains.id)
                WHERE commentchains.review=%s
                  AND commentchains.state!='empty'
                  AND commentchainchanges.uid=%s
                  AND (commentchainchanges.state='performed'
                       OR commentchainchanges.from_state=commentchains.state
                       OR commentchainchanges.from_type=commentchains.type)
                  AND commentchainchanges.{}""".format(condition),
            (self.__review_id, self.__author_id) + batch_id)
        self.__modified_comments = []
        for comment_id, new_type, new_state in cursor:
            self.__modified_comments.append(ModifiedComment(
                comment_id, new_type, new_state))

    def loadFileChanges(self, critic):
        cursor = critic.getDatabaseCursor()
        condition, batch_id = self.__queryCondition()
        cursor.execute(
            """SELECT reviewfiles.id, to_state
                 FROM reviewfiles
                 JOIN reviewfilechanges
                      ON (reviewfilechanges.file=reviewfiles.id)
                WHERE reviewfiles.review=%s
                  AND reviewfilechanges.uid=%s
                  AND (reviewfilechanges.state='performed'
                       OR reviewfilechanges.to_state!=reviewfiles.state)
                  AND reviewfilechanges.{}""".format(condition),
            (self.__review_id, self.__author_id) + batch_id)
        rows = cursor.fetchall()
        self.__reviewed_file_changes = set(
            filechange_id
            for filechange_id, to_state in rows
            if to_state == 'reviewed')
        self.__unreviewed_file_changes = set(
            filechange_id
            for filechange_id, to_state in rows
            if to_state == 'pending')

@Batch.cached(api.batch.InvalidBatchId)
def fetch(critic, batch_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, review, uid, comment, time
                        FROM batches
                       WHERE id=%s""",
                   (batch_id,))
    return Batch.make(critic, cursor)

def fetchAll(critic, review, author):
    conditions = ["TRUE"]
    values = []
    if review:
        conditions.append("review=%s")
        values.append(review.id)
    if author:
        conditions.append("uid=%s")
        values.append(author.id)
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, review, uid, comment, time
                        FROM batches
                       WHERE {}""".format(" AND ".join(conditions)),
                   values)
    return list(Batch.make(critic, cursor))

def fetchUnpublished(critic, review):
    author_id = critic.effective_user.id
    return Batch(None, review.id, author_id, None, None).wrap(critic)
