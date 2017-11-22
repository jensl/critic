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

from . import CreatedExtension
from .. import Transaction, Insert, InsertMany

from critic import api
from critic.background import extensiontasks


async def create_extension(
    transaction: Transaction, name: str, uri: str, publisher: Optional[api.user.User]
) -> CreatedExtension:
    critic = transaction.critic

    if publisher is None or publisher != critic.actual_user:
        api.PermissionDenied.raiseUnlessAdministrator(transaction.critic)

    try:
        await extensiontasks.scan_external(critic, uri)
    except extensiontasks.Error as error:
        raise api.extension.Error(str(error))

    extension = CreatedExtension(transaction)

    transaction.items.append(
        Insert("extensions", returning="id", collector=extension).values(
            name=name, publisher=publisher, uri=uri
        )
    )

    async def clone_extension() -> None:
        await extensiontasks.clone_external(critic, await extension)

    transaction.post_commit_callbacks.append(clone_extension)

    return extension
