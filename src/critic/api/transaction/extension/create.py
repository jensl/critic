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
from critic.background import extensiontasks

from ..base import TransactionBase
from ..createapiobject import CreateAPIObject


class CreateExtension(
    CreateAPIObject[api.extension.Extension], api_module=api.extension
):
    @staticmethod
    async def make(
        transaction: TransactionBase,
        name: str,
        url: str,
        publisher: Optional[api.user.User],
    ) -> api.extension.Extension:
        critic = transaction.critic

        if publisher is None or publisher != critic.actual_user:
            api.PermissionDenied.raiseUnlessAdministrator(transaction.critic)

        try:
            await extensiontasks.scan_external(critic, url)
        except extensiontasks.Error as error:
            raise api.extension.Error(str(error))

        extension = await CreateExtension(transaction).insert(
            name=name, publisher=publisher, uri=url
        )

        async def clone_extension() -> None:
            await extensiontasks.clone_external(critic, extension)

        transaction.post_commit_callbacks.append(clone_extension)

        return extension
