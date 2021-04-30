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
from typing import Callable, Tuple, Optional, Sequence

from .queryhelper import QueryHelper, QueryResult, join

logger = logging.getLogger(__name__)

from critic import api
from critic.api import extension as public
from critic import base
from critic.background import utils
from critic import extensions
from .apiobject import APIObjectImplWithId


PublicType = public.Extension
ArgumentsType = Tuple[int, str, Optional[int], str]


class Extension(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__name, self.__publisher_id, self.__url) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    async def key(self) -> str:
        publisher = await self.publisher
        if publisher is None:
            return self.name
        return f"{publisher.name}/{self.name}"

    @property
    async def path(self) -> Optional[str]:
        if not utils.is_background_service():
            return None
        publisher = await self.publisher
        base_dir = os.path.join(str(base.configuration()["paths.data"]), "extensions")
        if publisher is None:
            base_dir = os.path.join(base_dir, "system")
        else:
            base_dir = os.path.join(base_dir, "user", str(publisher.name))
        return os.path.join(base_dir, self.name + ".git")

    @property
    async def publisher(self) -> Optional[api.user.User]:
        if self.__publisher_id is None:
            return None
        return await api.user.fetch(self.critic, self.__publisher_id)

    @property
    def url(self) -> str:
        return self.__url

    @property
    async def default_version(self) -> api.extensionversion.ExtensionVersion:
        return await api.extensionversion.fetch(
            self.critic, extension=self, current=True
        )

    @property
    async def low_level(self) -> Optional[extensions.extension.Extension]:
        if self.__publisher_id is None:
            publisher_name = None
        else:
            publisher_name = (
                await api.user.fetch(self.critic, self.__publisher_id)
            ).name
        path = await self.path
        assert path is not None
        try:
            return extensions.extension.Extension(
                self.id, path, publisher_name, self.name
            )
        except extensions.extension.ExtensionError:
            return None

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    PublicType.getTableName(), "id", "name", "publisher", "uri"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic, extension_id: Optional[int], key: Optional[str]
) -> PublicType:
    if not api.critic.settings().extensions.enabled:
        raise api.extension.Error("Extension support not enabled")

    conditions = []
    if extension_id is not None:
        return await Extension.ensureOne(
            extension_id, queries.idFetcher(critic, Extension)
        )

    assert key is not None
    publisher_name, _, name = key.rpartition("/")
    conditions.append("name={name}")
    if not publisher_name:
        conditions.append("publisher IS NULL")
        publisher = None
    else:
        publisher = await api.user.fetch(critic, name=publisher_name)
        conditions.append("publisher={publisher}")

    return Extension.storeOne(
        await queries.query(
            critic, *conditions, name=name, publisher=publisher
        ).makeOne(Extension, public.InvalidKey(value=key))
    )


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    publisher: Optional[api.user.User],
    installed_by: Optional[api.user.User],
) -> Sequence[PublicType]:
    if not api.critic.settings().extensions.enabled:
        raise api.extension.Error("Extension support not enabled")

    joins = []
    conditions = []

    if publisher:
        conditions.append("publisher={publisher}")
    if installed_by:
        joins.append(join(extensioninstalls=["extension=extensions.id"]))
        conditions.append("extensioninstalls.uid={installed_by}")

    return Extension.store(
        await queries.query(critic, queries.formatQuery(*conditions, joins=joins)).make(
            Extension
        )
    )
