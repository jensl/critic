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

from typing import Collection

from ..review import CreateReviewObject
from ..base import TransactionBase

from critic import api


class CreateReply(CreateReviewObject[api.reply.Reply], api_module=api.reply):
    is_draft = True

    def __init__(
        self,
        transaction: TransactionBase,
        review: api.review.Review,
        comment: api.comment.Comment,
    ) -> None:
        super().__init__(transaction, review)
        self.comment = comment

    def scopes(self) -> Collection[str]:
        return (
            f"comments/{self.comment.id}",
            f"reviews/{self.review.id}/comments/{self.comment.id}",
        )

    @staticmethod
    async def make(
        transaction: TransactionBase,
        comment: api.comment.Comment,
        author: api.user.User,
        text: str,
    ) -> api.reply.Reply:
        return await CreateReply(transaction, await comment.review, comment).insert(
            chain=comment, uid=author, text=text
        )
