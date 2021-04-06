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
from abc import abstractmethod

import logging
from typing import Any, Awaitable, Callable, Optional, Sequence, overload

from critic.api.apiobject import FunctionRef

logger = logging.getLogger(__name__)

from critic import api


class Error(api.APIError, object_type="extension installation"):
    """Base exception for all errors related to the ExtensionInstallation
    class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid extensionversion id is used."""

    pass


class ExtensionInstallation(api.APIObjectWithId):
    """Representation of a single installation of a Critic extension"""

    @property
    @abstractmethod
    def id(self) -> int:
        """The extension installation's unique id"""
        ...

    @property
    @abstractmethod
    async def extension(self) -> api.extension.Extension:
        """The installed extension"""
        ...

    @property
    @abstractmethod
    async def version(self) -> api.extensionversion.ExtensionVersion:
        """The installed extension version, or None

        None is returned if this is a "live" installation, i.e. one that
        runs directly in the extension's source repository, or follows its
        master branch if it is a bare/remote repository."""
        ...

    @property
    @abstractmethod
    async def user(self) -> Optional[api.user.User]:
        """The installing user, or None

        None is returned if this is a "universal" installation, i.e. one that
        applies to all users."""
        ...

    @property
    @abstractmethod
    def is_universal(self) -> bool:
        """True if this is a "universal" installation"""
        ...

    @property
    async def manifest(self) -> Any:
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
    user: Optional[api.user.User] = None,
) -> Optional[ExtensionInstallation]:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension_name: str,
    user: Optional[api.user.User] = None,
) -> Optional[ExtensionInstallation]:
    ...


async def fetch(
    critic: api.critic.Critic,
    installation_id: Optional[int] = None,
    /,
    *,
    extension: Optional[api.extension.Extension] = None,
    extension_name: Optional[str] = None,
    user: Optional[api.user.User] = None,
) -> Optional[ExtensionInstallation]:
    """Fetch an ExtensionInstallation object by its unique id"""
    return await fetchImpl.get()(
        critic, installation_id, extension, extension_name, user
    )


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    user: Optional[api.user.User] = None,
) -> Sequence[ExtensionInstallation]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    version: api.extensionversion.ExtensionVersion,
    user: Optional[api.user.User] = None,
) -> Sequence[ExtensionInstallation]:
    ...


@overload
async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    user: Optional[api.user.User] = None,
) -> Sequence[ExtensionInstallation]:
    ...


async def fetchAll(
    critic: api.critic.Critic,
    /,
    *,
    extension: Optional[api.extension.Extension] = None,
    version: Optional[api.extensionversion.ExtensionVersion] = None,
    user: Optional[api.user.User] = None,
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
    return await fetchAllImpl.get()(critic, extension, version, user)


resource_name = "extensioninstallations"
table_name = "extensioninstalls"


fetchImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[int],
            Optional[api.extension.Extension],
            Optional[str],
            Optional[api.user.User],
        ],
        Awaitable[Optional[ExtensionInstallation]],
    ]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [
            api.critic.Critic,
            Optional[api.extension.Extension],
            Optional[api.extensionversion.ExtensionVersion],
            Optional[api.user.User],
        ],
        Awaitable[Sequence[ExtensionInstallation]],
    ]
] = FunctionRef()
