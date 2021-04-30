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

from typing import Optional

from ..base import TransactionBase
from ..item import Insert, Update, Delete
from ..modifier import Modifier
from ..accesstoken.mixin import ModifyUser as AccessTokenMixin
from ..extension.mixin import ModifyUser as ExtensionMixin
from ..extensioninstallation.mixin import ModifyUser as ExtensionInstallationMixin
from ..repositoryfilter.mixin import ModifyUser as RepositoryFilterMixin
from ..useremail.mixin import ModifyUser as UserEmailMixin
from ..setting.mixin import ModifyUser as SettingMixin
from ..usersshkey.mixin import ModifyUser as UserSSHKeyMixin
from .create import CreatedUser

from critic import api


class ModifyUser(
    AccessTokenMixin,
    ExtensionMixin,
    ExtensionInstallationMixin,
    RepositoryFilterMixin,
    SettingMixin,
    UserEmailMixin,
    UserSSHKeyMixin,
    Modifier[api.user.User],
):
    def __init__(self, transaction: TransactionBase, user: api.user.User) -> None:
        super().__init__(transaction, user)
        # transaction.lock("users", id=user.id)

    async def setFullname(self, value: str) -> None:
        await self.transaction.execute(Update(self.subject).set(fullname=value))

    async def setStatus(self, value: api.user.Status) -> None:
        await set_status(self.transaction, self.subject, value)

    async def setPassword(self, *, hashed_password: str) -> None:
        await self.transaction.execute(
            Update(self.subject).set(password=hashed_password)
        )

    async def resetPassword(self) -> None:
        await self.transaction.execute(Update(self.subject).set(password=None))

    # Roles
    # =====

    async def addRole(self, role: str) -> None:
        api.PermissionDenied.raiseUnlessSystem(self.transaction.critic)
        await self.transaction.execute(
            Insert("userroles").values(uid=self.subject, role=role)
        )

    async def deleteRole(self, role: str) -> None:
        api.PermissionDenied.raiseUnlessSystem(self.transaction.critic)
        await self.transaction.execute(
            Delete("userroles").where(uid=self.subject, role=role)
        )

    # Repository filters
    # ==================

    # Access tokens
    # =============

    # User settings
    # =============

    # External authentication
    # =======================

    async def connectTo(
        self, external_account: api.externalaccount.ExternalAccount
    ) -> None:
        await self.transaction.execute(Update(external_account).set(uid=self.subject))

    async def disconnectFrom(
        self, external_account: api.externalaccount.ExternalAccount
    ) -> None:
        if self.subject != await external_account.user:
            raise api.user.Error("external account belongs to a different user")
        await self.transaction.execute(Delete(external_account))

    # Email addresses
    # ===============

    # SSH keys
    # ========

    # Extensions
    # ==========

    @staticmethod
    async def create(
        transaction: TransactionBase,
        name: str,
        fullname: str,
        email: Optional[str],
        email_status: Optional[api.useremail.Status],
        hashed_password: Optional[str],
        status: api.user.Status,
        external_account: Optional[api.externalaccount.ExternalAccount],
    ) -> ModifyUser:
        modifier = ModifyUser(
            transaction,
            await CreatedUser.make(
                transaction,
                name,
                fullname,
                email,
                email_status,
                hashed_password,
                status,
                external_account,
            ),
        )

        if external_account is not None:
            await modifier.connectTo(external_account)

            if (
                transaction.critic.session_type == "user"
                and transaction.critic.actual_user is None
            ):
                # "Upgrade" existing user sessions (typically just the current one)
                # to belong to the newly created user.
                await transaction.execute(
                    Update("usersessions")
                    .set(uid=modifier.subject)
                    .where(external_uid=external_account)
                )

        return modifier


from .setstatus import set_status
