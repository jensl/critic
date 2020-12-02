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

from typing import Set

from critic import api
from .base import TransactionBase
from .createapiobject import CreateAPIObject
from .item import Delete
from .modifier import Modifier


class CreateLabeledAccessControlProfile(
    CreateAPIObject[api.labeledaccesscontrolprofile.LabeledAccessControlProfile],
    api_module=api.labeledaccesscontrolprofile,
):
    async def fetch(
        self, labels: str, /
    ) -> api.labeledaccesscontrolprofile.LabeledAccessControlProfile:
        return await api.labeledaccesscontrolprofile.fetch(
            self.critic, labels.split("|")
        )


class ModifyLabeledAccessControlProfile(
    Modifier[
        api.labeledaccesscontrolprofile.LabeledAccessControlProfile,
    ]
):
    async def delete(self) -> None:
        await self.transaction.execute(
            Delete("labeledaccesscontrolprofiles").where(labels=str(self.subject))
        )

    @staticmethod
    async def create(
        transaction: TransactionBase,
        labels: Set[str],
        profile: api.accesscontrolprofile.AccessControlProfile,
    ) -> ModifyLabeledAccessControlProfile:
        return ModifyLabeledAccessControlProfile(
            transaction,
            await CreateLabeledAccessControlProfile(transaction).insert(
                labels="|".join(sorted(labels)), profile=profile
            ),
        )
