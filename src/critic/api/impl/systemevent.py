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

from typing import Tuple, Optional, Sequence, Iterable

import json
import logging

logger = logging.getLogger(__name__)

from critic import api
from critic import base
from critic.base import dbaccess as base_dbaccess

from . import apiobject

WrapperType = api.systemevent.SystemEvent
ArgumentsType = Tuple[int, str, str, str, str, bool]


class SystemEvent(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = ["id", "category", "key", "title", "data", "handled"]

    def __init__(self, args: ArgumentsType):
        self.id, self.category, self.key, self.title, self.data, self.handled = args


@SystemEvent.cached
async def fetch(
    critic: api.critic.Critic,
    event_id: Optional[int],
    category: Optional[str],
    key: Optional[str],
) -> WrapperType:
    try:
        async with critic.query(
            f"SELECT 1 FROM {SystemEvent.table()} WHERE FALSE"
        ) as result:
            await result.ignore()
    except base_dbaccess.InvalidQueryError:
        # The |systemevents| table doesn't exist. This happens during upgrade
        # from a pre-2.0 system. Ignore the error here.
        assert event_id is None
        raise base.UninitializedDatabase()

    if event_id is not None:
        async with SystemEvent.query(
            critic, ["id={event_id}"], event_id=event_id
        ) as result:
            return await SystemEvent.makeOne(critic, result)

    assert category is not None
    assert key is not None

    async with SystemEvent.query(
        critic,
        f"""SELECT {SystemEvent.columns()}
              FROM {SystemEvent.table()}
             WHERE category={{category}}
               AND key={{key}}
          ORDER BY id DESC
             LIMIT 1""",
        category=category,
        key=key,
    ) as result:
        try:
            return await SystemEvent.makeOne(critic, result)
        except result.ZeroRowsInResult:
            raise api.systemevent.NotFound(category, key)


@SystemEvent.cachedMany
async def fetchMany(
    critic: api.critic.Critic, event_ids: Iterable[int]
) -> Sequence[WrapperType]:
    async with SystemEvent.query(
        critic, ["id=ANY({event_ids})"], event_ids=list(event_ids)
    ) as result:
        return await SystemEvent.make(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    category: Optional[str],
    key: Optional[str],
    pending: bool,
) -> Sequence[WrapperType]:
    conditions = []
    if category is not None:
        conditions.append("category={category}")
        if key is not None:
            conditions.append("key={key}")
    if pending:
        conditions.append("NOT handled")
    try:
        async with SystemEvent.query(
            critic, conditions, order_by="id DESC", category=category, key=key
        ) as result:
            return await SystemEvent.make(critic, result)
    except base_dbaccess.InvalidQueryError:
        # The |systemevents| doesn't exist. This happens during upgrade from a
        # pre-2.0 system.
        raise api.DatabaseSchemaError("Missing table: systemevents")
