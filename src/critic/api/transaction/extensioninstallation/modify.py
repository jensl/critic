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

from . import CreatedExtensionInstallation
from .. import Transaction, Delete, Update, Modifier

from critic import api
from critic import auth


class ModifyExtensionInstallation(
    Modifier[
        api.extensioninstallation.ExtensionInstallation, CreatedExtensionInstallation
    ]
):
    async def upgradeTo(self, version: api.extensionversion.ExtensionVersion) -> None:
        await auth.AccessControl.accessExtension(await self.real.extension, "install")

        if self.real.is_universal:
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        self.transaction.items.append(Update(self.real).set(version=version))

    async def deleteInstallation(self) -> None:
        await auth.AccessControl.accessExtension(await self.real.extension, "install")

        if self.real.is_universal:
            api.PermissionDenied.raiseUnlessAdministrator(self.transaction.critic)

        super().delete()

    @staticmethod
    async def create(
        transaction: Transaction,
        extension: api.extension.Extension,
        version: api.extensionversion.ExtensionVersion,
        user: api.user.User = None,
    ) -> ModifyExtensionInstallation:
        return ModifyExtensionInstallation(
            transaction,
            await create_extensioninstallation(transaction, extension, version, user),
        )


from .create import create_extensioninstallation
