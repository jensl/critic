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

import datetime
from typing import Tuple, Optional, Iterable, Sequence

from critic import api
from . import apiobject


WrapperType = api.reply.Reply
ArgumentsType = Tuple[int, int, Optional[int], int, str, datetime.datetime]


class Reply(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    table_name = "comments"
    column_names = ["id", "chain", "batch", "uid", "text", "time"]

    def __init__(self, args: ArgumentsType):
        (
            self.id,
            self.__comment_id,
            self.__batch_id,
            self.__author_id,
            self.text,
            self.timestamp,
        ) = args
        self.is_draft = self.__batch_id is None

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Reply)
        if self.__batch_id == other.__batch_id:
            return self.id < other.id
        return (self.__batch_id or 0) < (other.__batch_id or 0)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Reply) and self.id == other.id

    async def getComment(self, critic: api.critic.Critic) -> api.comment.Comment:
        return await api.comment.fetch(critic, self.__comment_id)

    async def getAuthor(self, critic: api.critic.Critic) -> api.user.User:
        return await api.user.fetch(critic, self.__author_id)


@Reply.cached
async def fetch(critic: api.critic.Critic, reply_id: int) -> WrapperType:
    async with Reply.query(critic, ["id={reply_id}"], reply_id=reply_id) as result:
        return await Reply.makeOne(critic, result)


@Reply.cachedMany
async def fetchMany(
    critic: api.critic.Critic, reply_ids: Iterable[int]
) -> Sequence[WrapperType]:
    async with Reply.query(
        critic, ["id=ANY({reply_ids})"], reply_ids=list(reply_ids)
    ) as result:
        return await Reply.make(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    comment: Optional[api.comment.Comment],
    author: Optional[api.user.User],
) -> Sequence[WrapperType]:
    conditions = []
    if comment is not None:
        conditions.append("chain={comment}")
    if author is not None:
        conditions.append("uid={author}")
    async with Reply.query(
        critic, conditions, comment=comment, author=author
    ) as result:
        return await Reply.make(critic, result)
