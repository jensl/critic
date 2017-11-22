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
from typing import Tuple, Optional, Sequence, Dict

logger = logging.getLogger(__name__)

from . import apiobject
from critic import api


WrapperType = api.extensioninstallation.ExtensionInstallation
ArgumentsType = Tuple[int, int, int, int]


class ExtensionInstallation(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.extensioninstallation.ExtensionInstallation
    table_name = "extensioninstalls"
    column_names = ["id", "extension", "version", "uid"]

    def __init__(self, args: ArgumentsType):
        (self.id, self.__extension_id, self.__version_id, self.__user_id) = args
        self.is_live = self.__version_id is None
        self.is_universal = self.__user_id is None

    async def getExtension(self, critic: api.critic.Critic) -> api.extension.Extension:
        return await api.extension.fetch(critic, self.__extension_id)

    async def getVersion(
        self, critic: api.critic.Critic
    ) -> Optional[api.extensionversion.ExtensionVersion]:
        if self.__version_id is None:
            return None
        return await api.extensionversion.fetch(critic, self.__version_id)

    async def getUser(self, critic: api.critic.Critic) -> Optional[api.user.User]:
        if self.__user_id is None:
            return None
        return await api.user.fetch(critic, self.__user_id)

    async def getRuntimePath(self, critic: api.critic.Critic) -> Optional[str]:
        if self.__version_id is None:
            extension = await self.getExtension(critic)
            return await extension.path
        version = await self.getVersion(critic)
        if version is None:
            return None
        return version.snapshot_path


@ExtensionInstallation.cached
async def fetch(
    critic: api.critic.Critic,
    installation_id: Optional[int],
    extension: Optional[api.extension.Extension],
    extension_name: Optional[str],
    user: Optional[api.user.User],
) -> Optional[WrapperType]:
    conditions = []
    if installation_id is not None:
        conditions.append(f"{ExtensionInstallation.table()}.id={{installation_id}}")
    if extension:
        conditions.append("extension={extension}")
        if user and not user.is_anonymous:
            conditions.append("uid={user} OR uid IS NULL")
        else:
            conditions.append("uid IS NULL")
    if extension_name:
        conditions.append("extensions.name={extension_name}")
    logger.debug(repr(conditions))
    async with ExtensionInstallation.query(
        critic,
        conditions,
        joins=["extensions ON (extensioninstalls.extension=extensions.id)"],
        installation_id=installation_id,
        extension=extension,
        user=user,
        extension_name=extension_name,
    ) as result:
        if installation_id is not None:
            return await ExtensionInstallation.makeOne(critic, result)
        else:
            installations = await ExtensionInstallation.make(critic, result)
    if not installations:
        return None
    if user and len(installations) > 1:
        assert len(installations) == 2, repr(installations)
        if installations[0].is_universal:
            # If two applied, and the first is universal, return the second.
            return installations[1]
    # In all other cases, return the first/only.
    return installations[0]


async def fetchAll(
    critic: api.critic.Critic,
    extension: Optional[api.extension.Extension],
    version: Optional[api.extensionversion.ExtensionVersion],
    user: Optional[api.user.User],
) -> Sequence[WrapperType]:
    conditions = []
    if extension:
        conditions.append("extension={extension}")
    if version:
        if isinstance(version, str) and version == "live":
            conditions.append("version IS NULL")
            version = None
        else:
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
    async with ExtensionInstallation.query(
        critic, conditions, extension=extension, version=version, user=user
    ) as result:
        installations = await ExtensionInstallation.make(critic, result)
    if not user:
        return installations
    # Need to filter per-extension duplicates that arrises when a user installs
    # an extension that is also installed universally. Both installations will
    # then "apply", and the version installed by the user themselves will win.
    per_extension: Dict[int, WrapperType] = {}
    for installation in installations:
        extension_id = installation._impl.__extension_id
        if extension_id in per_extension and installation.is_universal:
            # This installation is the second we see, and it's universal,
            # so we skip it. If it was the second and not universal, the
            # first will have been universal, so we overwrite that.
            continue
        per_extension[extension_id] = installation
    return [
        per_extension[installation._impl.__extension_id]
        for installation in installations
    ]
