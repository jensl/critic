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

import logging
from typing import Optional

logger = logging.getLogger(__name__)

from . import CreatedExtensionInstallation
from .. import Transaction, Finalizer, Insert

from critic import api
from critic import auth
from critic import dbaccess
from critic.background import extensiontasks


class Finalize(Finalizer):
    tables = {"pubsubreservations", "extensionpubsubreservations"}

    def __init__(self, installation: CreatedExtensionInstallation) -> None:
        self.installation = installation

    async def __call__(
        self, transaction: Transaction, cursor: dbaccess.TransactionCursor
    ) -> None:
        async with dbaccess.Query[str](
            cursor,
            """SELECT channel
                 FROM extensionsubscriptionroles AS esr
                 JOIN extensionroles AS er ON (er.id=esr.role)
                 JOIN extensioninstalls AS ei ON (ei.version=er.version)
                WHERE ei.id={install_id}""",
            install_id=self.installation,
        ) as result:
            channels = await result.scalars()

        if not channels:
            return

        for channel in channels:
            reservation_id = await cursor.insert(
                "pubsubreservations", {"channel": channel}, returning="reservation_id"
            )
            await cursor.insert(
                "extensionpubsubreservations",
                {"install_id": self.installation, "reservation_id": reservation_id},
            )

        transaction.wakeup_service("extensionhost")
        transaction.wakeup_service("pubsub")


async def create_extensioninstallation(
    transaction: Transaction,
    extension: api.extension.Extension,
    version: api.extensionversion.ExtensionVersion,
    user: Optional[api.user.User],
) -> CreatedExtensionInstallation:
    await auth.AccessControl.accessExtension(extension, "install")

    assert user is None or user.type == "regular"

    if user is None:
        # "Universal" installation: affects all users.
        api.PermissionDenied.raiseUnlessAdministrator(transaction.critic)
    else:
        api.PermissionDenied.raiseUnlessUser(transaction.critic, user)

    manifest = await version.manifest
    for setting_data in manifest.low_level.settings:
        try:
            await api.systemsetting.fetch(transaction.critic, key=setting_data.key)
        except api.systemsetting.InvalidKey:
            pass
        else:
            continue

        transaction.createSystemSetting(
            setting_data.key,
            setting_data.description,
            setting_data.value,
            privileged=setting_data.privileged,
        )

    installation = CreatedExtensionInstallation(transaction)

    transaction.items.append(
        Insert("extensioninstalls", returning="id", collector=installation).values(
            extension=extension, version=version, uid=user
        )
    )

    transaction.finalizers.add(Finalize(installation))

    return installation
