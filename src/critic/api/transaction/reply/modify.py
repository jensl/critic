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

from ..item import Delete, Update
from ..base import TransactionBase
from ..modifier import Modifier
from .create import CreateReply

from critic import api


class ModifyReply(Modifier[api.reply.Reply]):
    def __raiseUnlessDraft(self, action: str) -> None:
        if not self.subject.is_draft:
            raise api.reply.Error("Published replies cannot be " + action)

    async def setText(self, text: str) -> None:
        self.__raiseUnlessDraft("edited")
        await self.transaction.execute(Update(self.subject).set(text=text))

    async def delete(self) -> None:
        self.__raiseUnlessDraft("deleted")
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        comment: api.comment.Comment,
        author: api.user.User,
        text: str,
    ) -> ModifyReply:
        return ModifyReply(
            transaction, await CreateReply.make(transaction, comment, author, text)
        )
