# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

from typing import Collection, Tuple, Optional, Sequence, Iterable

from critic import api
from critic.api import labeledaccesscontrolprofile as public
from critic.api.apiobject import Actual
from .apiobject import APIObjectImpl
from .queryhelper import QueryHelper

PublicType = public.LabeledAccessControlProfile


class LabeledAccessControlProfile(PublicType, APIObjectImpl, module=public):
    def __init__(self, critic: api.critic.Critic, labels: str, profile_id: int):
        super().__init__(critic)
        self.__labels = labels
        self.__profile_id = profile_id

    def __str__(self) -> str:
        return self.__labels

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, LabeledAccessControlProfile)
            and self.__labels == other.__labels
        )

    def getCacheKeys(self) -> Collection[object]:
        return (self.__labels,)

    async def refresh(self: Actual) -> Actual:
        return self

    @property
    def labels(self) -> Collection[str]:
        return tuple(self.__labels.split("|"))

    @property
    async def profile(self) -> api.accesscontrolprofile.AccessControlProfile:
        return await api.accesscontrolprofile.fetch(self.critic, self.__profile_id)


RowType = Tuple[str, int]
queries = QueryHelper[RowType](
    PublicType.getTableName(), "labels", "profile", default_order_by=["labels ASC"]
)


def make(critic: api.critic.Critic, row: RowType) -> LabeledAccessControlProfile:
    labels, profile_id = row
    return LabeledAccessControlProfile(critic, labels, profile_id)


@public.fetchImpl
async def fetch(critic: api.critic.Critic, labels: Iterable[str]) -> PublicType:
    labels = "|".join(sorted(labels))
    return await LabeledAccessControlProfile.ensureOne(
        labels, queries.itemFetcher(critic, make, "labels")
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    profile: Optional[api.accesscontrolprofile.AccessControlProfile],
) -> Sequence[PublicType]:
    return LabeledAccessControlProfile.store(
        await queries.query(critic, profile=profile).make(make)
    )
