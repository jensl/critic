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

from typing import Iterable, Sequence

from critic import dbaccess

from . import Transaction, InsertMany, Update, Delete, Modifier
from .user import CreatedUserObject
from critic import api


class CreatedRepositoryFilter(CreatedUserObject, api_module=api.repositoryfilter):
    @staticmethod
    def make(
        transaction: Transaction,
        user: api.user.User,
        filter_type: api.repositoryfilter.FilterType,
        repository: api.repository.Repository,
        path: str,
        default_scope: bool,
        scopes: Iterable[api.reviewscope.ReviewScope],
        delegates: Iterable[api.user.User],
    ) -> CreatedRepositoryFilter:
        api.PermissionDenied.raiseUnlessUser(transaction.critic, user)
        created_filter = CreatedRepositoryFilter(transaction, user)
        created_filter.insert(
            uid=user,
            repository=repository,
            type=filter_type,
            path=path,
            default_scope=default_scope,
        )
        scopes_values: Sequence[dbaccess.Parameters] = [
            dict(filter=created_filter, scope=scope) for scope in scopes
        ]
        if scopes_values:
            transaction.items.append(
                InsertMany("repositoryfilterscopes", ["filter", "scope"], scopes_values)
            )
        delegates_values: Sequence[dbaccess.Parameters] = [
            dict(filter=created_filter, uid=delegate) for delegate in delegates
        ]
        if delegates_values:
            transaction.items.append(
                InsertMany(
                    "repositoryfilterdelegates", ["filter", "uid"], delegates_values
                )
            )
        return created_filter


class ModifyRepositoryFilter(
    Modifier[api.repositoryfilter.RepositoryFilter, CreatedRepositoryFilter]
):
    def setDelegates(self, value: Iterable[api.user.User]) -> None:
        self.transaction.items.append(
            Update(self.real).set(
                delegate=",".join(delegate.name for delegate in value if delegate.name)
            )
        )

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(
        transaction: Transaction,
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
            CreatedRepositoryFilter.make(
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
