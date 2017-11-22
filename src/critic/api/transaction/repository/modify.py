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
import re
from typing import Any, Iterable

logger = logging.getLogger(__name__)

from . import CreatedRepository
from .. import (
    Transaction,
    Query,
    Update,
    Insert,
    Modifier,
    Delete,
    protocol,
    requireAdministrator,
    requireSystem,
)
from ..branch import validate_branch_name
from ..repositorysetting import CreatedRepositorySetting
from critic import api


class ModifyRepository(Modifier[api.repository.Repository, CreatedRepository]):
    def setIsReady(self) -> None:
        self.transaction.items.append(Update(self.subject).set(ready=True))
        self.updates["is_ready"] = True

    async def createBranch(
        self,
        branch_type: api.branch.BranchType,
        name: str,
        commits: Iterable[api.commit.Commit],
        *,
        head: api.commit.Commit = None,
        base_branch: api.branch.Branch = None,
        output: str = None,
        is_creating_review: bool = False,
        pendingrefupdate_id: int = None,
    ) -> ModifyBranch:
        return await ModifyBranch.create(
            self.transaction,
            self.real,
            branch_type,
            name,
            commits,
            head,
            base_branch,
            output,
            is_creating_review,
            pendingrefupdate_id,
        )

    async def modifyBranch(self, branch: api.branch.Branch) -> ModifyBranch:
        assert await branch.repository == self.subject
        return ModifyBranch(self.transaction, branch)

    @requireSystem
    async def trackBranch(
        self, url: str, remote_name: str, local_name: str
    ) -> ModifyTrackedBranch:
        # Check if the branch already exists. If it does, its name must be fine.
        # If it doesn't already exist, ensure that the branch name is valid. If
        # not, the tracking will fail to create it either way, so best not set
        # the tracking up at all.
        if isinstance(self.subject, CreatedRepository):
            # Act as if no refs exist in just created repository. This will
            # typically be the case.
            pass
        else:
            try:
                await self.subject.resolveRef("refs/heads/" + local_name)
            except api.repository.InvalidRef:
                await validate_branch_name(self.subject, local_name)

        delay = api.critic.settings().repositories.branch_update_interval

        if not isinstance(self.subject, CreatedRepository):
            self.transaction.wakeup_service("branchtracker")

        return await ModifyTrackedBranch.create(
            self.transaction, self.subject, url, remote_name, local_name, delay
        )

    @requireSystem
    def trackTags(self, url: str) -> None:
        self.transaction.items.append(
            Insert("trackedbranches").values(
                repository=self.subject,
                local_name="*",
                remote=url,
                remote_name="*",
                forced=True,
                delay=api.critic.settings().repositories.tags_update_interval,
            )
        )

        if not isinstance(self.subject, CreatedRepository):
            self.transaction.wakeup_service("branchtracker")

    # Repository settings
    # ===================

    @requireAdministrator
    async def defineSetting(
        self, scope: str, name: str, value: Any
    ) -> ModifyRepositorySetting:
        token = "[A-Za-z0-9_]+"

        if not (1 <= len(scope) <= 64):
            raise api.repositorysetting.InvalidScope(
                "Scope must be between 1 and 64 characters long"
            )
        if not re.match(f"^{token}$", scope):
            raise api.repositorysetting.InvalidScope(
                "Scope must contain only characters from the set [A-Za-z0-9_]"
            )

        if not (1 <= len(name) <= 256):
            raise api.repositorysetting.InvalidName(
                "Name must be between 1 and 256 characters long"
            )
        if not re.match(f"^{token}(?:\\.{token})*$", name):
            raise api.repositorysetting.InvalidName(
                "Name must consist of '.'-separated tokens containing only "
                "characters from the set [A-Za-z0-9_]"
            )

        critic = self.transaction.critic

        if isinstance(self.subject, api.repository.Repository):
            try:
                await api.repositorysetting.fetch(
                    critic, repository=self.real, scope=scope, name=name
                )
            except api.repositorysetting.NotDefined:
                pass
            else:
                raise api.repositorysetting.Error(
                    f"Repository setting already defined: {scope}:{name}"
                )

        return ModifyRepositorySetting.create(
            self.transaction, self.subject, scope, name, value
        )

    @requireAdministrator
    def modifySetting(
        self, setting: api.repositorysetting.RepositorySetting
    ) -> ModifyRepositorySetting:
        return ModifyRepositorySetting(self.transaction, setting)

    @requireAdministrator
    async def deleteRepository(self) -> None:
        transaction = self.transaction
        critic = transaction.critic

        for review in await api.review.fetchAll(critic, repository=self.real):
            await transaction.modifyReview(review).deleteReview(
                deleting_repository=True
            )

        super().delete()

    @staticmethod
    def create(transaction: Transaction, name: str, path: str) -> ModifyRepository:
        return ModifyRepository(transaction, create_repository(transaction, name, path))

    async def create_deleted_payload(self) -> protocol.DeletedAPIObject:
        repository = self.real
        return protocol.DeletedRepository(
            self.resource_name, repository.id, repository.name, repository.path
        )


from .create import create_repository
from ..branch import CreatedBranch, ModifyBranch
from ..repositorysetting import ModifyRepositorySetting
from ..trackedbranch import ModifyTrackedBranch
