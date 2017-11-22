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

from . import Transaction, Query, Insert, LazyAPIObject, Modifier
from critic import api


class CreatedLabeledAccessControlProfile(
    LazyAPIObject, api_module=api.labeledaccesscontrolprofile
):
    @staticmethod
    async def fetch(
        critic: api.critic.Critic, labels: str
    ) -> api.labeledaccesscontrolprofile.LabeledAccessControlProfile:
        return await api.labeledaccesscontrolprofile.fetch(critic, labels.split("|"))


class ModifyLabeledAccessControlProfile(
    Modifier[
        api.labeledaccesscontrolprofile.LabeledAccessControlProfile,
        CreatedLabeledAccessControlProfile,
    ]
):
    def delete(self) -> None:
        self.transaction.tables.add("labeledaccesscontrolprofiles")
        self.transaction.items.append(
            Query(
                """DELETE
                     FROM labeledaccesscontrolprofiles
                    WHERE labels={labels}""",
                labels=str(self.subject),
            )
        )

    @staticmethod
    def create(
        transaction: Transaction,
        labels: Set[str],
        profile: api.accesscontrolprofile.AccessControlProfile,
    ) -> ModifyLabeledAccessControlProfile:
        labeled_profile = CreatedLabeledAccessControlProfile(transaction)

        transaction.tables.add("labeledaccesscontrolprofiles")
        transaction.items.append(
            Insert(
                "labeledaccesscontrolprofiles",
                returning="labels",
                collector=labeled_profile,
            ).values(labels="|".join(sorted(labels)), profile=profile)
        )

        return ModifyLabeledAccessControlProfile(transaction, labeled_profile)
