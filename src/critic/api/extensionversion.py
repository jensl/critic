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

from typing import Literal, Optional, Protocol, Collection, Sequence, Union, overload

from critic import api
from critic import extensions


class Error(api.APIError, object_type="extension version"):
    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised when an invalid extension version id is used."""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised when an invalid extension version name is used."""

    pass


PackageType = Literal["python"]


class ExtensionVersion(api.APIObject):
    @property
    def id(self) -> int:
        return self._impl.id

    @property
    async def extension(self) -> api.extension.Extension:
        return await self._impl.getExtension(self.critic)

    @property
    def is_live(self) -> bool:
        return self._impl.name is None

    @property
    def name(self) -> Optional[str]:
        return self._impl.name

    @property
    def sha1(self) -> str:
        return self._impl.sha1

    @property
    def snapshot_path(self) -> str:
        return self._impl.snapshot_path

    class PythonPackage(Protocol):
        @property
        def package_type(self) -> Literal["python"]:
            ...

        class Entrypoint(Protocol):
            @property
            def name(self) -> str:
                ...

            @property
            def target(self) -> str:
                ...

        @property
        def entrypoints(self) -> Collection[Entrypoint]:
            ...

        @property
        def dependencies(self) -> Collection[str]:
            ...

    class Role(Protocol):
        @property
        def description(self) -> str:
            ...

    class ExecutesServerSide(Role, Protocol):
        @property
        def entrypoint(self) -> Optional[str]:
            ...

    class Endpoint(ExecutesServerSide, Protocol):
        @property
        def name(self) -> str:
            ...

    class Subscription(ExecutesServerSide, Protocol):
        @property
        def channel(self) -> str:
            ...

        @property
        def reserved(self) -> bool:
            ...

    class UIAddon(Role, Protocol):
        @property
        def name(self) -> str:
            ...

        @property
        def bundle_js(self) -> Optional[str]:
            ...

        @property
        def bundle_css(self) -> Optional[str]:
            ...

    class Manifest(Protocol):
        @property
        def package(self) -> Union[ExtensionVersion.PythonPackage]:
            ...

        @property
        def endpoints(self) -> Collection[ExtensionVersion.Endpoint]:
            ...

        @property
        def subscriptions(self) -> Collection[ExtensionVersion.Subscription]:
            ...

        @property
        def ui_addons(self) -> Collection[ExtensionVersion.UIAddon]:
            ...

        @property
        def low_level(self) -> extensions.manifest.Manifest:
            ...

    @property
    async def manifest(self) -> Manifest:
        return await self._impl.getManifest(self)


@overload
async def fetch(critic: api.critic.Critic, version_id: int, /) -> ExtensionVersion:
    ...


@overload
async def fetch(
    critic: api.critic.Critic,
    /,
    *,
    extension: api.extension.Extension,
    name: Optional[str],
) -> ExtensionVersion:
    ...


async def fetch(
    critic: api.critic.Critic,
    version_id: int = None,
    *,
    extension: api.extension.Extension = None,
    name: str = None,
) -> ExtensionVersion:
    from .impl import extensionversion as impl

    return await impl.fetch(critic, version_id, extension, name)


async def fetchAll(
    critic: api.critic.Critic, /, *, extension: api.extension.Extension = None
) -> Sequence[ExtensionVersion]:
    from .impl import extensionversion as impl

    return await impl.fetchAll(critic, extension)


resource_name = table_name = "extensionversions"
