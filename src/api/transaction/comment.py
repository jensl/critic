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

class ModifyComment(object):
    def __init__(self, transaction, comment):
        self.transaction = transaction
        self.comment = comment

    def __raiseUnlessDraft(self, action):
        if not self.comment.is_draft:
            raise api.comment.CommentError(
                "Published comments cannot be " + action)

    def setText(self, text):
        self.__raiseUnlessDraft("edited")

        if not text.strip():
            raise api.comment.CommentError("Empty comment")

        self.transaction.tables.add("comments")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE comments
                      SET comment=%s
                    WHERE id in (SELECT first_comment
                                   FROM commentchains
                                  WHERE id=%s)""",
                (text, self.comment.id)))

    def addReply(self, author, text, callback=None):
        assert isinstance(author, api.user.User)
        assert isinstance(text, str)

        if self.comment.is_draft:
            raise api.comment.CommentError(
                "Draft comments cannot be replied to")

        for reply in self.comment.replies:
            if reply.is_draft:
                raise api.comment.CommentError(
                    "Comment already has a draft reply")

        critic = self.transaction.critic

        # Users are not (generally) allowed to create comments as other users.
        api.PermissionDenied.raiseUnlessUser(critic, author)

        reply = CreatedReply(critic, self.comment, callback)

        self.transaction.tables.add("comments")
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO comments (chain, uid, state, comment)
                   VALUES (%s, %s, 'draft', %s)
                RETURNING id""",
                (self.comment.id, author.id, text),
                collector=reply))

        return reply

    def modifyReply(self, reply):
        from reply import ModifyReply
        assert isinstance(reply, api.reply.Reply)
        assert reply.comment == self.comment

        api.PermissionDenied.raiseUnlessUser(self.transaction.critic,
                                             reply.author)

        return ModifyReply(self.transaction, reply)

    def delete(self):
        critic = self.transaction.critic

        api.PermissionDenied.raiseUnlessUser(critic, self.comment.author)

        self.__raiseUnlessDraft("deleted")

        self.transaction.tables.add("commentchains")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM commentchains
                    WHERE id=%s""",
                (self.comment.id,)))

class CreatedReply(api.transaction.LazyAPIObject):
    def __init__(self, critic, comment, callback=None):
        super(CreatedReply, self).__init__(
            critic, api.reply.fetch, callback)
        self.comment = comment
