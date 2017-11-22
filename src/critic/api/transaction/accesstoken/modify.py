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

from . import CreatedAccessToken
from .. import Update, Delete, Modifier, Transaction

from critic import api


class ModifyAccessToken(Modifier[api.accesstoken.AccessToken, CreatedAccessToken]):
    def setTitle(self, value: str) -> None:
        self.transaction.items.append(Update(self.real).set(title=value))

    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    async def modifyProfile(self) -> ModifyAccessControlProfile:
        profile = await self.subject.profile
        if not profile:
            raise api.accesstoken.Error("Token has no profile")
        return ModifyAccessControlProfile(self.transaction, profile)

    @staticmethod
    def create(
        transaction: Transaction,
        access_type: api.accesstoken.AccessType,
        title: Optional[str],
        *,
        user: api.user.User = None
    ) -> ModifyAccessToken:
        return ModifyAccessToken(
            transaction, create_accesstoken(transaction, access_type, title, user)
        )


from .create import create_accesstoken
from ..accesscontrolprofile import ModifyAccessControlProfile
