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

import json
from typing import Union, Tuple, Any

from . import Transaction, Update, Delete, LazyAPIObject, Modifier
from critic import api


def valueAsJSON(value: Any) -> str:
    try:
        return json.dumps(value)
    except TypeError as error:
        raise api.repositorysetting.Error("Value is not JSON compatible: %s" % error)


class CreatedRepositorySetting(LazyAPIObject, api_module=api.repositorysetting):
    def __init__(
        self,
        transaction: Transaction,
        repository: Union[api.repository.Repository, CreatedRepository],
    ) -> None:
        super().__init__(transaction)
        self.repository = repository

    def scopes(self) -> LazyAPIObject.Scopes:
        return (f"repositories/{self.repository.id}",)

    @staticmethod
    def make(
        transaction: Transaction,
        repository: Union[api.repository.Repository, CreatedRepository],
        scope: str,
        name: str,
        value: Any,
    ) -> CreatedRepositorySetting:
        return CreatedRepositorySetting(transaction, repository).insert(
            repository=repository, scope=scope, name=name, value=valueAsJSON(value),
        )


class ModifyRepositorySetting(
    Modifier[api.repositorysetting.RepositorySetting, CreatedRepositorySetting]
):
    def setValue(self, value: Any) -> None:
        self.transaction.items.append(Update(self.real).set(value=valueAsJSON(value)))

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(
        transaction: Transaction,
        repository: Union[api.repository.Repository, CreatedRepository],
        scope: str,
        name: str,
        value: Any,
    ) -> ModifyRepositorySetting:
        return ModifyRepositorySetting(
            transaction,
            CreatedRepositorySetting.make(transaction, repository, scope, name, value),
        )


from .repository import CreatedRepository
