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

from critic import api
from ..base import TransactionBase
from ..modifier import Modifier
from .create import CreateExtension


class ModifyExtension(Modifier[api.extension.Extension]):
    def __init__(
        self,
        transaction: TransactionBase,
        subject: api.extension.Extension,
        user: Optional[api.user.User],
    ) -> None:
        super().__init__(transaction, subject)
        self.user = user

    # async def update(self) -> None:
    #     raise Exception("NOT IMPLEMENTED")

    async def setURL(self, value: str) -> ModifyExtension:
        async with self.update() as update:
            update.set(url=value)
        return self

    async def deleteExtension(self, *, forced: bool = False) -> None:
        from critic.background import extensiontasks

        critic = self.transaction.critic
        extension = self.subject

        installations = await api.extensioninstallation.fetchAll(
            critic, extension=extension
        )
        if len(installations):
            if not forced:
                raise api.extension.Error("Extension has active installations")
            api.PermissionDenied.raiseUnlessAdministrator(critic)

        await super().delete()

        async def delete_extension() -> None:
            await extensiontasks.delete_extension(critic, extension)

        self.transaction.pre_commit_callbacks.append(delete_extension)

    @staticmethod
    async def create(
        transaction: TransactionBase,
        name: str,
        uri: str,
        *,
        publisher: Optional[api.user.User] = None
    ) -> ModifyExtension:
        return ModifyExtension(
            transaction,
            await CreateExtension.make(transaction, name, uri, publisher),
            publisher,
        )
