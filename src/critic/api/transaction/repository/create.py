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

from . import CreatedRepository
from .. import Insert, Transaction
from critic import api


def create_repository(
    transaction: Transaction, name: str, path: str
) -> CreatedRepository:
    if not path.endswith(".git"):
        raise api.repository.Error("Invalid repository path")

    repository = CreatedRepository(transaction)

    transaction.tables.add("repositories")
    transaction.items.append(
        Insert("repositories", returning="id", collector=repository).values(
            name=name, path=path
        )
    )

    # The maintenance service creates the repository on disk.
    # transaction.wakeup_service("maintenance")

    return repository
