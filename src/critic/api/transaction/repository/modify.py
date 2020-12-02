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

logger = logging.getLogger(__name__)

from critic import api
from ..item import Update
from ..modifier import Modifier
from ..protocol import DeletedRepository
from ..utils import requireAdministrator
from ..base import TransactionBase
from ..branch.mixin import ModifyRepository as BranchMixin
from ..repositorysetting.mixin import ModifyRepository as RepositorySettingMixin
from ..trackedbranch.mixin import ModifyRepository as TrackedBranchMixin
from .create import CreateRepository


class ModifyRepository(
    BranchMixin,
    RepositorySettingMixin,
    TrackedBranchMixin,
    Modifier[api.repository.Repository],
):
    async def setIsReady(self) -> None:
        await self.transaction.execute(Update(self.subject).set(ready=True))
        self.updates["is_ready"] = True

    # Repository settings
    # ===================

    @requireAdministrator
    async def delete(self) -> None:
        transaction = self.transaction
        critic = transaction.critic

        for review in await api.review.fetchAll(critic, repository=self.subject):
            await transaction.modifyReview(review).deleteReview(  # type: ignore
                deleting_repository=True
            )

        await super().delete()

    @staticmethod
    async def create(
        transaction: TransactionBase, name: str, path: str
    ) -> ModifyRepository:
        return ModifyRepository(
            transaction, await CreateRepository.make(transaction, name, path)
        )

    async def create_deleted_payload(self) -> DeletedRepository:
        repository = self.subject
        return DeletedRepository(
            self.resource_name, repository.id, repository.name, repository.path
        )
