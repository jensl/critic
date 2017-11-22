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
from typing import Optional, Sequence, Union, Literal, overload

logger = logging.getLogger(__name__)

from critic import api
from critic import extensions


class Error(api.APIError, object_type="extension installation"):
    """Base exception for all errors related to the ExtensionInstallation
       class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid extensionversion id is used."""

    pass


class ExtensionInstallation(api.APIObject):
    """Representation of a single installation of a Critic extension"""

    def __repr__(self) -> str:
        return f"ExtensionInstallation(id={self.id}, extension_id={self._impl._ExtensionInstallation__extension_id})"

    @property
    def id(self) -> int:
        """The extension installation's unique id"""
        return self._impl.id

    @property
    async def extension(self) -> api.extension.Extension:
        """The installed extension"""
        return await self._impl.getExtension(self.critic)

    @property
    async def version(self) -> api.extensionversion.ExtensionVersion:
        """The installed extension version, or None

           None is returned if this is a "live" installation, i.e. one that
           runs directly in the extension's source repository, or follows its
           master branch if it is a bare/remote repository."""
        return await self._impl.getVersion(self.critic)

    @property
    def is_live(self) -> bool:
        """True if this is a "live" installation"""
        return self._impl.is_live

    @property
    async def runtime_path(self) -> str:
        return await self._impl.getRuntimePath(self.critic)

    @property
    async def user(self) -> Optional[api.user.User]:
        """The installing user, or None

           None is returned if this is a "universal" installation, i.e. one that
           applies to all users."""
        return await self._impl.getUser(self.critic)

    @property
    def is_universal(self) -> bool:
        """True if this is a "universal" installation"""
        return self._impl.is_universal

    @property
    async def manifest(self) -> extensions.manifest.Manifest:
        version = await self.version
        return (await version.manifest).low_level


@overload
async def fetch(
    critic: api.critic.Critic, installation_id: int, /
) -> ExtensionInstallation:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    user: api.user.User = None,
) -> Optional[ExtensionInstallation]:
    ...


@overload
async def fetch(
    critic: api.critic.Critic, /, *, extension_name: str, user: api.user.User = None
) -> Optional[ExtensionInstallation]:
    ...


async def fetch(
    critic: api.critic.Critic,
    installation_id: int = None,
    /,
    *,
    extension: api.extension.Extension = None,
    extension_name: str = None,
    user: api.user.User = None,
) -> Optional[ExtensionInstallation]:
    """Fetch an ExtensionInstallation object by its unique id"""
    from .impl import extensioninstallation as impl

    return await impl.fetch(critic, installation_id, extension, extension_name, user)


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    user: api.user.User = None,
) -> Sequence[ExtensionInstallation]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    version: api.extensionversion.ExtensionVersion,
    user: api.user.User = None,
) -> Sequence[ExtensionInstallation]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic, /, *, user: api.user.User = None,
) -> Sequence[ExtensionInstallation]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension = None,
    version: api.extensionversion.ExtensionVersion = None,
    user: api.user.User = None,
) -> Sequence[ExtensionInstallation]:
    """Fetch ExtensionInstallation objects for all installed extensions

       If |extensions| is not None, include only installations of the given
       extension.

       If |version| is not None, include only installations of the given
       extension version. Note: this implies including only installations of
       the extension |version.extension|, and because of that, |extension|
       must be None if |version| is not None.

       If |user| is not None, include only installations affecting the given
       user. Note: this will include both installations the user has created
       themselves and any universal installations that affect them. If |user|
       the anonymous user, only universal installations are included."""
    from .impl import extensioninstallation as impl

    return await impl.fetchAll(critic, extension, version, user)


resource_name = table_name = "extensioninstallations"
