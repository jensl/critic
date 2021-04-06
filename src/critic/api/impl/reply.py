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
from typing import Callable, Tuple, Optional, Sequence

from critic import api
from critic.api import reply as public
from .queryhelper import QueryHelper, QueryResult
from .apiobject import APIObjectImplWithId


PublicType = public.Reply
ArgumentsType = Tuple[int, int, Optional[int], int, str, datetime.datetime]


class Reply(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__comment_id,
            self.__batch_id,
            self.__author_id,
            self.__text,
            self.__timestamp,
        ) = args
        self.__is_draft = self.__batch_id is None
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def is_draft(self) -> bool:
        return self.__is_draft

    @property
    async def comment(self) -> api.comment.Comment:
        return await api.comment.fetch(self.critic, self.__comment_id)

    @property
    async def author(self) -> api.user.User:
        return await api.user.fetch(self.critic, self.__author_id)

    @property
    def timestamp(self) -> datetime.datetime:
        return self.__timestamp

    @property
    def text(self) -> str:
        return self.__text
        """The reply's text"""
        ...

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Reply)
        if self.__batch_id == other.__batch_id:
            return self.id < other.id
        return (self.__batch_id or 0) < (other.__batch_id or 0)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "comment", "batch", "author", "text", "time"
)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, reply_id: int) -> PublicType:
    return await Reply.ensureOne(reply_id, queries.idFetcher(critic, Reply))


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, reply_ids: Sequence[int]
) -> Sequence[PublicType]:
    return await Reply.ensure(reply_ids, queries.idsFetcher(critic, Reply))


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    comment: Optional[api.comment.Comment],
    author: Optional[api.user.User],
) -> Sequence[PublicType]:
    return Reply.store(
        await queries.query(critic, comment=comment, author=author).make(Reply)
    )
