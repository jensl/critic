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
from typing import Callable, Tuple, Optional, Sequence, Dict

from .queryhelper import QueryHelper, QueryResult, join

logger = logging.getLogger(__name__)

from critic import api
from critic.api import extensioninstallation as public
from .apiobject import APIObjectImplWithId


PublicType = public.ExtensionInstallation
ArgumentsType = Tuple[int, int, int, int]


class ExtensionInstallation(PublicType, APIObjectImplWithId, module=public):
    def update(self, args: ArgumentsType) -> int:
        (self.__id, self.__extension_id, self.__version_id, self.__user_id) = args
        return self.__id

    @property
    def id(self) -> int:
        return self.__id

    @property
    async def extension(self) -> api.extension.Extension:
        return await api.extension.fetch(self.critic, self.__extension_id)

    @property
    def extension_id(self) -> int:
        return self.__extension_id

    @property
    async def version(self) -> api.extensionversion.ExtensionVersion:
        return await api.extensionversion.fetch(self.critic, self.__version_id)

    @property
    def is_universal(self) -> bool:
        return self.__user_id is None

    @property
    async def user(self) -> Optional[api.user.User]:
        if self.__user_id is None:
            return None
        return await api.user.fetch(self.critic, self.__user_id)

    @classmethod
    def getQueryByIds(
        cls,
    ) -> Callable[[api.critic.Critic, Sequence[int]], QueryResult[ArgumentsType]]:
        return queries.queryByIds


queries = QueryHelper[ArgumentsType](
    ExtensionInstallation.getTableName(), "id", "extension", "version", "uid"
)


@public.fetchImpl
async def fetch(
    critic: api.critic.Critic,
    installation_id: Optional[int],
    extension: Optional[api.extension.Extension],
    extension_name: Optional[str],
    user: Optional[api.user.User],
) -> Optional[PublicType]:
    if installation_id is not None:
        return await ExtensionInstallation.ensureOne(
            installation_id, queries.idFetcher(critic, ExtensionInstallation)
        )
    joins = []
    conditions = []
    if extension:
        conditions.append("extension={extension}")
        if user and not user.is_anonymous:
            conditions.append("uid={user} OR uid IS NULL")
        else:
            conditions.append("uid IS NULL")
    if extension_name:
        joins.append(join(extensions=["extensions.id=extensioninstalls.extension"]))
        conditions.append("extensions.name={extension_name}")
    installations = ExtensionInstallation.store(
        await queries.query(
            critic,
            queries.formatQuery(*conditions, joins=joins),
            extension=extension,
            user=user,
            extension_name=extension_name,
        ).make(ExtensionInstallation)
    )
    if not installations:
        return None
    if user and len(installations) > 1:
        assert len(installations) == 2, repr(installations)
        if installations[0].is_universal:
            # If two applied, and the first is universal, return the second.
            return installations[1]
    # In all other cases, return the first/only.
    return installations[0]


@public.fetchAllImpl
async def fetchAll(
    critic: api.critic.Critic,
    extension: Optional[api.extension.Extension],
    version: Optional[api.extensionversion.ExtensionVersion],
    user: Optional[api.user.User],
) -> Sequence[PublicType]:
    conditions = []
    if extension:
        conditions.append("extension={extension}")
    if version:
        conditions.append("version={version}")
    if user:
        if user.is_anonymous:
            conditions.append("uid IS NULL")
            user = None
        else:
            # Include universal installations (uid IS NULL) here as well, since
            # those will apply for a given user as well, unless they have an
            # overriding installation of their own, which we'll sort out later.
            conditions.append("(uid={user} OR uid IS NULL)")
    installations = ExtensionInstallation.store(
        await queries.query(
            critic,
            *conditions,
            extension=extension,
            version=version,
            user=user,
        ).make(ExtensionInstallation)
    )
    if not user:
        return installations
    # Need to filter per-extension duplicates that arrises when a user installs
    # an extension that is also installed universally. Both installations will
    # then "apply", and the version installed by the user themselves will win.
    per_extension: Dict[int, PublicType] = {}
    for installation in installations:
        extension_id = installation.extension_id
        if extension_id in per_extension and installation.is_universal:
            # This installation is the second we see, and it's universal,
            # so we skip it. If it was the second and not universal, the
            # first will have been universal, so we overwrite that.
            continue
        per_extension[extension_id] = installation
    return [per_extension[installation.extension_id] for installation in installations]
