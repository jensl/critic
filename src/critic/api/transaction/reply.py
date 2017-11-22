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

from __future__ import annotations

from typing import Union

from . import Transaction, Delete, Update, Modifier, LazyAPIObject
from .review import CreatedReviewObject

from critic import api


class CreatedReply(CreatedReviewObject, api_module=api.reply):
    is_draft = True

    def __init__(
        self,
        transaction: api.transaction.Transaction,
        review: api.review.Review,
        comment: api.comment.Comment,
    ) -> None:
        super().__init__(transaction, review)
        self.comment = comment

    def scopes(self) -> LazyAPIObject.Scopes:
        return super().scopes() + (f"comments/{self.comment.id}",)


class ModifyReply(Modifier[api.reply.Reply, CreatedReply]):
    def __init__(
        self, transaction: Transaction, reply: Union[api.reply.Reply, CreatedReply]
    ) -> None:
        self.transaction = transaction
        self.reply = reply
        transaction.lock("comments", id=reply.id)

    def __raiseUnlessDraft(self, action: str) -> None:
        if not self.reply.is_draft:
            raise api.reply.Error("Published replies cannot be " + action)

    async def setText(self, text: str) -> None:
        self.__raiseUnlessDraft("edited")
        self.transaction.items.append(Update(self.reply).set(text=text))

    def delete(self) -> None:
        self.__raiseUnlessDraft("deleted")
        self.transaction.items.append(Delete(self.reply))
