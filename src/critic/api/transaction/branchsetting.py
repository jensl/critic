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
from typing import Any

from . import Transaction, Update, Delete, Modifier
from .branch import CreatedBranchObject

from critic import api


class CreatedBranchSetting(CreatedBranchObject, api_module=api.branchsetting):
    pass


class ModifyBranchSetting(
    Modifier[api.branchsetting.BranchSetting, CreatedBranchSetting]
):
    def setValue(self, value: Any) -> None:
        self.transaction.items.append(
            Update(self.real).set(value=self.valueAsJSON(value))
        )

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def valueAsJSON(value: Any) -> str:
        try:
            return json.dumps(value)
        except TypeError as error:
            raise api.branchsetting.Error("Value is not JSON compatible: %s" % error)
