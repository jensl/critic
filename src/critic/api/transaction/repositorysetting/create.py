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

from typing import Any

from critic import api
from ..base import TransactionBase
from ..repository import CreateRepositoryObject
from . import value_as_json


class CreateRepositorySetting(
    CreateRepositoryObject[api.repositorysetting.RepositorySetting],
    api_module=api.repositorysetting,
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        repository: api.repository.Repository,
        scope: str,
        name: str,
        value: Any,
    ) -> api.repositorysetting.RepositorySetting:
        return await CreateRepositorySetting(transaction, repository).insert(
            repository=repository,
            scope=scope,
            name=name,
            value=value_as_json(value),
        )
