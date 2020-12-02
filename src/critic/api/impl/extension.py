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

import logging
import os
from typing import Tuple, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api import extension as public
from critic import base
from critic.background import utils
from critic import extensions
from . import apiobject


WrapperType = api.extension.Extension
ArgumentsType = Tuple[int, str, Optional[int], str]


class Extension(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = WrapperType
    column_names = ["id", "name", "publisher", "uri"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.name, self.__publisher_id, self.url) = args

    async def getKey(self, critic: api.critic.Critic) -> str:
        publisher = await self.getPublisher(critic)
        if publisher is None:
            return self.name
        return f"{publisher.name}/{self.name}"

    async def getPath(self, critic: api.critic.Critic) -> Optional[str]:
        if not utils.is_background_service():
            return None
        publisher = await self.getPublisher(critic)
        base_dir = os.path.join(str(base.configuration()["paths.data"]), "extensions")
        if publisher is None:
            base_dir = os.path.join(base_dir, "system")
        else:
            base_dir = os.path.join(base_dir, "user", str(publisher.name))
        return os.path.join(base_dir, self.name + ".git")

    async def getPublisher(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.__publisher_id is None:
            return None
        return await api.user.fetch(critic, self.__publisher_id)

    async def getInstallation(
        self, critic: api.critic.Critic
    ) -> Optional[api.extensioninstallation.ExtensionInstallation]:
        async with api.critic.Query[int](
            critic,
            """SELECT ei.id
                 FROM extensioninstalls AS ei
                WHERE ei.extension={extension}
                  AND (ei.uid={user} OR ei.uid IS NULL)
             ORDER BY ei.uid NULLS LAST
                LIMIT 1""",
            extension=self.id,
            user=critic.effective_user,
        ) as result:
            try:
                install_id = await result.scalar()
            except result.ZeroRowsInResult:
                return None
        return await api.extensioninstallation.fetch(critic, install_id)

    async def getLowLevel(
        self, critic: api.critic.Critic
    ) -> Optional[extensions.extension.Extension]:
        if self.__publisher_id is None:
            publisher_name = None
        else:
            publisher_name = (await api.user.fetch(critic, self.__publisher_id)).name
        path = await self.getPath(critic)
        assert path is not None
        try:
            return extensions.extension.Extension(
                self.id, path, publisher_name, self.name
            )
        except extensions.extension.ExtensionError:
            return None


@public.fetchImpl
@Extension.cached
async def fetch(
    critic: api.critic.Critic, extension_id: Optional[int], key: Optional[str]
) -> WrapperType:
    if not api.critic.settings().extensions.enabled:
        raise api.extension.Error("Extension support not enabled")

    conditions = []
    if extension_id is not None:
        conditions.append("extensions.id={extension_id}")
        publisher_name, extension_name = None, None
    else:
        assert key is not None
        publisher_name, _, extension_name = key.rpartition("/")
        conditions.append("extensions.name={extension_name}")
        if not publisher_name:
            conditions.append("publisher IS NULL")
        else:
            conditions.append("users.name={publisher_name}")

    async with Extension.query(
        critic,
        conditions,
        extension_id=extension_id,
        extension_name=extension_name,
        publisher_name=publisher_name,
    ) as result:
        try:
            return await Extension.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if key is not None:
                raise api.extension.InvalidKey(value=key)
            raise


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    publisher: Optional[api.user.User],
    installed_by: Optional[api.user.User],
) -> Sequence[WrapperType]:
    if not api.critic.settings().extensions.enabled:
        raise api.extension.Error("Extension support not enabled")

    tables = [Extension.table()]
    conditions = []

    if publisher:
        conditions.append("publisher={publisher}")
    if installed_by:
        tables.append("extensioninstalls ON (extension=extensions.id)")
        conditions.append("uid={installed_by}")

    async with Extension.query(
        critic, conditions, publisher=publisher, installed_by=installed_by
    ) as result:
        return await Extension.make(critic, result)
