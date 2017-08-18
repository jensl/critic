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
import apiobject

class Reply(apiobject.APIObject):
    wrapper_class = api.reply.Reply

    def __init__(self, reply_id, state, comment_id, batch_id, author_id,
                 timestamp, text):
        self.id = reply_id
        self.is_draft = state == "draft"
        self.__comment_id = comment_id
        self.__batch_id = batch_id
        self.__author_id = author_id
        self.timestamp = timestamp
        self.text = text

    def __cmp__(self, other):
        return cmp(self.__batch_id, other.__batch_id)

    def getComment(self, critic):
        return api.comment.fetch(critic, self.__comment_id)

    def getAuthor(self, critic):
        return api.user.fetch(critic, self.__author_id)

    @staticmethod
    def refresh(critic, tables, cached_replies):
        if "comments" not in tables:
            return

        Reply.updateAll(
            critic,
            """SELECT id, state, chain, batch, uid, time, comment
                 FROM comments
                WHERE id=ANY (%s)""",
            cached_replies)

@Reply.cached()
def fetch(critic, reply_id):
    draft_user_id = critic.actual_user.id if critic.actual_user else None
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT comments.id, comments.state, chain, comments.batch,
                             comments.uid, comments.time, comment
                        FROM comments
                        JOIN commentchains ON (commentchains.id=comments.chain)
                       WHERE comments.id=%s
                         AND (comments.state='current' OR comments.uid=%s)
                         AND comments.state!='deleted'
                         AND commentchains.first_comment!=comments.id""",
                   (reply_id, draft_user_id))
    try:
        return next(Reply.make(critic, cursor))
    except StopIteration:
        raise api.reply.InvalidReplyId(reply_id)

def fetchForComment(critic, chain_id):
    draft_user_id = critic.actual_user.id if critic.actual_user else None
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT comments.id, comments.state, chain, comments.batch,
                             comments.uid, comments.time, comment
                        FROM comments
                        JOIN commentchains ON (commentchains.id=comments.chain)
                       WHERE (comments.state='current' OR comments.uid=%s)
                         AND comments.state!='deleted'
                         AND commentchains.id=%s
                         AND commentchains.first_comment!=comments.id
                    ORDER BY comments.batch ASC""",
                   (draft_user_id, chain_id))
    return list(Reply.make(critic, cursor))
