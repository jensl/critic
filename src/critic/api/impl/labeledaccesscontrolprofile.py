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

from typing import Tuple, Optional, Sequence, Iterable, List

from critic import api
from . import apiobject

public = api.labeledaccesscontrolprofile

WrapperType = public.LabeledAccessControlProfile
ArgumentsType = Tuple[str, int]


class LabeledAccessControlProfile(apiobject.APIObject[WrapperType, ArgumentsType, str]):
    wrapper_class = WrapperType
    column_names = ["labels", "profile"]

    def __init__(self, args: ArgumentsType) -> None:
        labels, self.__profile_id = args
        self.labels = tuple(labels.split("|"))

    async def getAccessControlProfile(
        self, critic: api.critic.Critic
    ) -> api.accesscontrolprofile.AccessControlProfile:
        return await api.accesscontrolprofile.fetch(critic, self.__profile_id)


async def fetch(critic: api.critic.Critic, labels: Iterable[str]) -> WrapperType:
    async with LabeledAccessControlProfile.query(
        critic,
        ["labels={labels}"],
        labels="|".join(sorted(str(label) for label in labels)),
    ) as result:
        return await LabeledAccessControlProfile.makeOne(critic, result)


async def fetchAll(
    critic: api.critic.Critic,
    profile: Optional[api.accesscontrolprofile.AccessControlProfile],
) -> Sequence[WrapperType]:
    conditions: List[str] = []

    if profile:
        conditions.append("profile={profile}")

    async with LabeledAccessControlProfile.query(
        critic, [conditions], order_by="labels ASC", profile=profile
    ) as result:
        return await LabeledAccessControlProfile.make(critic, result)
