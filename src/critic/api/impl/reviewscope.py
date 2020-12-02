# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2020 the Critic contributors, Opera Software ASA
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

from typing import Tuple, Optional, Sequence, Union

from critic import api
from critic.api import reviewscope as public
from . import apiobject

WrapperType = api.reviewscope.ReviewScope
ArgumentsType = Tuple[int, str]


class ReviewScope(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = ["id", "name"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.name) = args


@public.fetchImpl
@ReviewScope.cached
async def fetch(
    critic: api.critic.Critic, scope_id: Optional[int], name: Optional[str]
) -> WrapperType:
    conditions = []
    if scope_id is not None:
        conditions.append("id={scope_id}")
    elif name is not None:
        conditions.append("name={name}")
    async with ReviewScope.query(
        critic, conditions, scope_id=scope_id, name=name
    ) as result:
        try:
            return await ReviewScope.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if name is not None:
                raise api.repositorysetting.InvalidName(name)
            raise


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    filter: Optional[
        Union[api.repositoryfilter.RepositoryFilter, api.reviewfilter.ReviewFilter]
    ],
) -> Sequence[WrapperType]:
    joins = []
    conditions = []
    if isinstance(filter, api.repositoryfilter.RepositoryFilter):
        joins.append(
            "repositoryfilterscopes ON (repositoryfilterscopes.scope=reviewscopes.id)"
        )
        conditions.append("repositoryfilterscopes.filter={filter}")
    if isinstance(filter, api.reviewfilter.ReviewFilter):
        joins.append("reviewfilterscopes ON (reviewfilterscopes.scope=reviewscopes.id)")
        conditions.append("reviewfilterscopes.filter={filter}")
    async with ReviewScope.query(
        critic, conditions, joins=joins, filter=filter
    ) as result:
        return await ReviewScope.make(critic, result)
