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
from typing import Optional

logger = logging.getLogger(__name__)

from critic import api
from ..base import TransactionBase
from ..item import Delete, Update
from ..modifier import Modifier
from .create import CreatedUserSSHKey


class ModifyUserSSHKey(Modifier[api.usersshkey.UserSSHKey]):
    async def setComment(self, value: str) -> None:
        await self.transaction.execute(Update(self.subject).set(comment=value))

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    @staticmethod
    async def create(
        transaction: TransactionBase,
        user: api.user.User,
        key_type: str,
        key: str,
        comment: Optional[str] = None,
    ) -> ModifyUserSSHKey:
        return ModifyUserSSHKey(
            transaction,
            await CreatedUserSSHKey.make(transaction, user, key_type, key, comment),
        )
