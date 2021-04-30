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

from ..base import TransactionBase
from ..branch import CreateBranchObject
from . import value_as_json

from critic import api


class CreateBranchSetting(
    CreateBranchObject[api.branchsetting.BranchSetting], api_module=api.branchsetting
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        branch: api.branch.Branch,
        scope: str,
        name: str,
        value: Any,
    ) -> api.branchsetting.BranchSetting:
        return await CreateBranchSetting(transaction, branch).insert(
            branch=branch, scope=scope, name=name, value=value_as_json(value)
        )