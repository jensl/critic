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

from typing import Iterable

from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from ..item import Update, Delete
from .create import CreateRepositoryFilter


class ModifyRepositoryFilter(Modifier[api.repositoryfilter.RepositoryFilter]):
    async def setDelegates(self, value: Iterable[api.user.User]) -> None:
        await self.transaction.execute(
            Update(self.subject).set(
                delegate=",".join(delegate.name for delegate in value if delegate.name)
            )
        )

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        user: api.user.User,
        filter_type: api.repositoryfilter.FilterType,
        repository: api.repository.Repository,
        path: str,
        default_scope: bool,
        scopes: Iterable[api.reviewscope.ReviewScope],
        delegates: Iterable[api.user.User],
    ) -> ModifyRepositoryFilter:
        return ModifyRepositoryFilter(
            transaction,
            await CreateRepositoryFilter.make(
                transaction,
                user,
                filter_type,
                repository,
                path,
                default_scope,
                scopes,
                delegates,
            ),
        )
