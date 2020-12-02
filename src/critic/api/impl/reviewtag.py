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

from typing import Tuple, Optional, Iterable, Sequence

from critic import api
from critic.api import reviewtag as public
from . import apiobject

WrapperType = api.reviewtag.ReviewTag
ArgumentsType = Tuple[int, str, str]


class ReviewTag(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.reviewtag.ReviewTag
    column_names = ["id", "name", "description"]

    def __init__(self, args: ArgumentsType) -> None:
        (self.id, self.name, self.description) = args


@public.fetchImpl
@ReviewTag.cached
async def fetch(
    critic: api.critic.Critic, reviewtag_id: Optional[int], name: Optional[str]
) -> WrapperType:
    if reviewtag_id is not None:
        condition = "id={reviewtag_id}"
    else:
        assert name is not None
        condition = "name={name}"
    async with ReviewTag.query(
        critic,
        [condition],
        reviewtag_id=reviewtag_id,
        name=name,
    ) as result:
        return await ReviewTag.makeOne(critic, result)


@public.fetchManyImpl
@ReviewTag.cachedMany
async def fetchMany(
    critic: api.critic.Critic,
    reviewtag_ids: Optional[Iterable[int]],
    names: Optional[Iterable[str]] = None,
) -> Sequence[WrapperType]:
    if reviewtag_ids is not None:
        condition = "{id=reviewtag_ids:array}"
        reviewtag_ids = list(reviewtag_ids)
    else:
        assert names is not None
        condition = "{name=names:array}"
        names = list(names)
    async with ReviewTag.query(
        critic,
        [condition],
        reviewtag_ids=reviewtag_ids,
        names=names,
    ) as result:
        return await ReviewTag.make(critic, result)


@public.fetchAllImpl
async def fetchAll(critic: api.critic.Critic) -> Sequence[WrapperType]:
    async with ReviewTag.query(critic) as result:
        return await ReviewTag.make(critic, result)
