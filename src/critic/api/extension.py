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

from typing import Any, Awaitable, Callable, Sequence, Optional, overload

from critic import api
from critic.api.apiobject import FunctionRef


class Error(api.APIError, object_type="extension"):
    """Base exception for all errors related to the Extension class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when a invalid extension id is used"""

    pass


class InvalidKey(api.InvalidItemError, Error, item_type="key"):
    """Raised when an invalid extension key is used"""

    pass


class Extension(api.APIObject):
    """Representation of a Critic extension"""

    @property
    def id(self) -> int:
        """The extension's unique id"""
        return self._impl.id

    @property
    def name(self) -> str:
        """The extension's name"""
        return self._impl.name

    @property
    async def key(self) -> str:
        """The extension's unique key

        For a system extension, the key is the extension's name.  For other
        extensions, the key is the publisher's username followed by a slash
        followed by the extension's name."""
        return await self._impl.getKey(self.critic)

    @property
    async def path(self) -> str:
        """The extensions's primary file system path

        None is returned if the extension could not be located. This value is
        only available to code running in a background service (i.e. with
        access to the "right" file system.)"""
        return await self._impl.getPath(self.critic)

    @property
    async def publisher(self) -> Optional[api.user.User]:
        """The extension's publisher

        The user that published the extension.  This may not be the author
        (who may not be a user of this Critic system.)

        None if this is a system extension."""
        return await self._impl.getPublisher(self.critic)

    @property
    def url(self) -> str:
        """The extension's repository URL if hosted remotely."""
        return self._impl.url

    @property
    async def versions(self) -> Sequence[api.extensionversion.ExtensionVersion]:
        return await api.extensionversion.fetchAll(self.critic, extension=self)

    @property
    def default_version(self) -> api.extensionversion.ExtensionVersion:
        """The default extension version

        This is typically the version whose extension description and other
        metadata should be presented as the extension's true metadata."""
        return self._impl.getDefaultVersion()

    @property
    async def live_version(self) -> api.extensionversion.ExtensionVersion:
        """The live extension version"""
        return await api.extensionversion.fetch(self.critic, extension=self, name=None)

    @property
    async def installation(
        self,
    ) -> Optional[api.extensioninstallation.ExtensionInstallation]:
        """The current user's installation of the extension, or None

        The installation is returned as an api.extensioninstallation.
        ExtensionInstallation object.

        This is None if the current user does not have an active installation
        of this extension."""
        return await api.extensioninstallation.fetch(
            self.critic, extension=self, user=self.critic.effective_user
        )

    @property
    async def low_level(self) -> Optional[Any]:
        """Low-level interface for managing the extension

        The interface is returned as an extensions.extension.Extension
        object. This interface should typically not be used directly.

        None is returned if the on-disk extension is missing, inaccessible or
        otherwise broken."""
        return await self._impl.getLowLevel(self.critic)


@overload
async def fetch(critic: api.critic.Critic, extension_id: int, /) -> Extension:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, key: str) -> Extension:
    ...


async def fetch(
    critic: api.critic.Critic,
    extension_id: Optional[int] = None,
    /,
    *,
    key: Optional[str] = None,
) -> Extension:
    """Fetch an Extension object with the given extension id or key

    Exactly one of the 'extension_id' and 'key' arguments can be used.

    Exceptions:

      InvalidId: if 'extension_id' is used and is not a valid extension id.
      InvalidKey: if 'key' is used and is not a valid extensions key."""
    return await fetchImpl.get()(critic, extension_id, key)


async def fetchAll(
    critic: api.critic.Critic,
    publisher: Optional[api.user.User] = None,
    installed_by: Optional[api.user.User] = None,
) -> Sequence[Extension]:
    """Fetch Extension objects for all extensions in the system

    If 'publisher' is not None, it must be an api.user.User object, and only
    extensions published by this user are returned.

    If 'installed_by' is not None, it must be an api.user.User object, and
    only extensions that this user has installed are returned. This may
    include extensions that are universally installed (i.e. installed for all
    users, and not by this user directly.) If the user object represents the
    anonymous user, only universally installed extensions are returned."""
    return await fetchAllImpl.get()(critic, publisher, installed_by)


resource_name = table_name = "extensions"


fetchImpl: FunctionRef[
    Callable[[api.critic.Critic, Optional[int], Optional[str]], Awaitable[Extension]]
] = FunctionRef()
fetchAllImpl: FunctionRef[
    Callable[
        [api.critic.Critic, Optional[api.user.User], Optional[api.user.User]],
        Awaitable[Sequence[Extension]],
    ]
] = FunctionRef()
