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

class ModifyReply(object):
    def __init__(self, transaction, reply):
        self.transaction = transaction
        self.reply = reply

    def __raiseUnlessDraft(self, action):
        if not self.reply.is_draft:
            raise api.reply.ReplyError(
                "Published replies cannot be " + action)

    def setText(self, text):
        self.__raiseUnlessDraft("edited")

        if not text.strip():
            raise api.reply.ReplyError("Empty reply")

        self.transaction.tables.add("comments")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE comments
                      SET comment=%s
                    WHERE id=%s""",
                (text, self.reply.id)))

    def delete(self):
        self.__raiseUnlessDraft("deleted")

        self.transaction.tables.add("comments")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM comments
                    WHERE id=%s""",
                (self.reply.id,)))
