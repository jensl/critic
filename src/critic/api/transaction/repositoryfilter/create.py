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

from critic import dbaccess

from ..base import TransactionBase
from ..item import InsertMany
from ..user import CreatedUserObject
from critic import api


class CreateRepositoryFilter(
    CreatedUserObject[api.repositoryfilter.RepositoryFilter],
    api_module=api.repositoryfilter,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        user: api.user.User,
        filter_type: api.repositoryfilter.FilterType,
        repository: api.repository.Repository,
        path: str,
        default_scope: bool,
        scopes: Iterable[api.reviewscope.ReviewScope],
        delegates: Iterable[api.user.User],
    ) -> api.repositoryfilter.RepositoryFilter:
        api.PermissionDenied.raiseUnlessUser(transaction.critic, user)
        created_filter = await CreateRepositoryFilter(transaction, user).insert(
            uid=user,
            repository=repository,
            type=filter_type,
            path=path,
            default_scope=default_scope,
        )
        if scopes:
            await transaction.execute(
                InsertMany(
                    "repositoryfilterscopes",
                    ["filter", "scope"],
                    (
                        dbaccess.parameters(filter=created_filter, scope=scope)
                        for scope in scopes
                    ),
                )
            )
        if delegates:
            await transaction.execute(
                InsertMany(
                    "repositoryfilterdelegates",
                    ["filter", "uid"],
                    (
                        dbaccess.parameters(filter=created_filter, uid=delegate)
                        for delegate in delegates
                    ),
                )
            )
        return created_filter
