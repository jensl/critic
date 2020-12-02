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
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from ..item import Update, Delete
from ..base import TransactionBase
from ..modifier import Modifier
from ..accesscontrolprofile.modify import ModifyAccessControlProfile
from .create import CreateAccessToken

from critic import api


class ModifyAccessToken(Modifier[api.accesstoken.AccessToken]):
    async def setTitle(self, value: str) -> None:
        await self.transaction.execute(Update(self.subject).set(title=value))

    async def delete(self) -> None:
        await self.transaction.execute(Delete(self.subject))

    async def modifyProfile(self) -> ModifyAccessControlProfile:
        profile = await self.subject.profile
        if not profile:
            raise api.accesstoken.Error("Token has no profile")
        return ModifyAccessControlProfile(self.transaction, profile)

    @staticmethod
    async def create(
        transaction: TransactionBase,
        access_type: api.accesstoken.AccessType,
        title: Optional[str],
        *,
        user: Optional[api.user.User] = None
    ) -> Tuple[ModifyAccessToken, str]:
        token, token_value = await CreateAccessToken.make(
            transaction, access_type, title, user
        )
        return (
            ModifyAccessToken(
                transaction,
                token,
            ),
            token_value,
        )
