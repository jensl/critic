# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2019 the Critic contributors, Opera Software ASA
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

from critic import api
from critic import auth
from ..base import TransactionBase
from ..item import Update
from ..modifier import Modifier
from .create import CreateExtensionInstallation


class ModifyExtensionInstallation(
    Modifier[api.extensioninstallation.ExtensionInstallation]
):
    async def upgradeTo(self, version: api.extensionversion.ExtensionVersion) -> None:
        await auth.AccessControl.accessExtension(
            await self.subject.extension, "install"
        )

        if self.subject.is_universal:
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        async with self.update(version=version.id) as update:
            update.set(version=version)

    async def deleteInstallation(self) -> None:
        await auth.AccessControl.accessExtension(
            await self.subject.extension, "install"
        )

        if self.subject.is_universal:
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        await super().delete()

    @staticmethod
    async def create(
        transaction: TransactionBase,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
        user: Optional[api.user.User] = None,
    ) -> ModifyExtensionInstallation:
        return ModifyExtensionInstallation(
            transaction,
            await CreateExtensionInstallation.make(
                transaction, extension, version, user
            ),
        )
