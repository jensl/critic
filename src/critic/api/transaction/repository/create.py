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
from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateRepository(
    CreateAPIObject[api.repository.Repository], api_module=api.repository
):
    @staticmethod
    async def make(
        transaction: TransactionBase, name: str, path: str
    ) -> api.repository.Repository:
        if not path.endswith(".git"):
            raise api.repository.Error("Invalid repository path")

        return await CreateRepository(transaction).insert(name=name, path=path)
