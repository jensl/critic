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

import logging
from typing import Any, Callable, Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api import systemevent as public
from .apiobject import APIObjectImplWithId
from .queryhelper import QueryHelper, QueryResult

PublicType = public.SystemEvent
ArgumentsType = Tuple[int, str, str, str, str, bool]


class SystemEvent(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (
            self.__id,
            self.__category,
            self.__key,
            self.__title,
            self.__data,
            self.__handled,
        ) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def category(self) -> str:
        return self.__category

    @property
    def key(self) -> str:
        return self.__key

    @property
    def title(self) -> str:
        return self.__title

    @property
    def data(self) -> Any:
        return self.__data

    @property
    def handled(self) -> bool:
        return self.__handled

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(),
    "id",
    "category",
    "key",
    "title",
    "data",
    "handled",
    default_order_by=["id DESC"],
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    event_id: Optional[int],
    category: Optional[str],
    key: Optional[str],
) -> PublicType:
    if event_id is not None:
        return await SystemEvent.ensureOne(
            event_id, queries.idFetcher(critic, SystemEvent)
        )
    assert category is not None and key is not None
    return SystemEvent.storeOne(
        await queries.query(
            critic,
            queries.formatQuery("category={category}", "key={key}", limit=1),
            category=category,
            key=key,
        ).makeOne(SystemEvent, public.NotFound(category, key))
    )


@public.fetchManyImpl
async def fetchMany(
    critic: api.critic.Critic, event_ids: Sequence[int]
) -> Sequence[PublicType]:
    return await SystemEvent.ensure(event_ids, queries.idsFetcher(critic, SystemEvent))


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    category: Optional[str],
    key: Optional[str],
    pending: bool,
) -> Sequence[PublicType]:
    conditions = []
    if category is not None:
        conditions.append("category={category}")
        if key is not None:
            conditions.append("key={key}")
    if pending:
        conditions.append("NOT handled")
    return SystemEvent.store(
        await queries.query(
            critic,
            *conditions,
            category=category,
            key=key,
        ).make(SystemEvent)
    )
