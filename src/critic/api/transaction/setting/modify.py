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

from typing import Any, Optional

from critic import api
from ..base import TransactionBase
from ..item import Update, Delete
from ..modifier import Modifier
from . import valueAsJSON
from .create import CreatedSetting


class ModifySetting(Modifier[api.setting.Setting]):
    async def _check(self) -> None:
        user = await self.subject.user
        if user:
            api.PermissionDenied.raiseUnlessUser(self.critic, user)
        else:
            api.PermissionDenied.raiseUnlessAdministrator(self.critic)

    async def setValue(self, value: Any) -> None:
        await self._check()
        await self.transaction.execute(
            Update(self.subject).set(value=valueAsJSON(value))
        )

    async def delete(self) -> None:
        await self._check()
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        scope: str,
        name: str,
        value: Any,
        value_bytes: Optional[bytes],
        user: Optional[api.user.User],
        repository: Optional[api.repository.Repository],
        branch: Optional[api.branch.Branch],
        review: Optional[api.review.Review],
        extension: Optional[api.extension.Extension],
    ) -> ModifySetting:
        return ModifySetting(
            transaction,
            await CreatedSetting.make(
                transaction,
                scope,
                name,
                value,
                value_bytes,
                user,
                repository,
                branch,
                review,
                extension,
            ),
        )
