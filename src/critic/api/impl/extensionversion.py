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

from dataclasses import dataclass, field
from typing import Tuple, Optional, Sequence

from . import apiobject
from ... import api

from critic import extensions
from critic.extensions import getExtensionSnapshotPath
from critic.extensions.manifest.pythonpackage import PythonPackage
from critic.background import extensiontasks


@dataclass(frozen=True)
class EntrypointImpl:
    name: str
    target: str


@dataclass(frozen=True)
class PythonPackageImpl:
    package_type: str = field(default="python", init=False)
    entrypoints: Sequence[
        api.extensionversion.ExtensionVersion.PythonPackage.Entrypoint
    ]
    dependencies: Sequence[str]


@dataclass(frozen=True)
class RoleImpl:
    description: str


@dataclass(frozen=True)
class ExecutesServerSide(RoleImpl):
    entrypoint: Optional[str]


@dataclass(frozen=True)
class EndpointImpl(ExecutesServerSide):
    name: str


@dataclass(frozen=True)
class UIAddonImpl(RoleImpl):
    name: str
    bundle_js: Optional[str]
    bundle_css: Optional[str]


@dataclass(frozen=True)
class SubscriptionImpl(ExecutesServerSide):
    channel: str
    reserved: bool


@dataclass(frozen=True)
class ManifestImpl:
    package: api.extensionversion.ExtensionVersion.PythonPackage
    endpoints: Sequence[api.extensionversion.ExtensionVersion.Endpoint]
    ui_addons: Sequence[api.extensionversion.ExtensionVersion.UIAddon]
    subscriptions: Sequence[api.extensionversion.ExtensionVersion.Subscription]
    low_level: extensions.extension.Manifest


WrapperType = api.extensionversion.ExtensionVersion
ArgumentsType = Tuple[int, int, str, str]


class ExtensionVersion(apiobject.APIObject[WrapperType, ArgumentsType, int]):
    wrapper_class = api.extensionversion.ExtensionVersion
    column_names = ["id", "extension", "name", "sha1"]

    __manifest: Optional[api.extensionversion.ExtensionVersion.Manifest]

    def __init__(self, args: ArgumentsType):
        (self.id, self.__extension_id, self.name, self.sha1) = args
        self.__manifest = None

    async def getExtension(self, critic: api.critic.Critic) -> api.extension.Extension:
        return await api.extension.fetch(critic, self.__extension_id)

    @property
    def snapshot_path(self) -> str:
        return getExtensionSnapshotPath(self.sha1)

    async def getManifest(
        self, wrapper: WrapperType
    ) -> api.extensionversion.ExtensionVersion.Manifest:
        if self.__manifest is None:
            critic = wrapper.critic
            low_level = await extensiontasks.read_manifest(wrapper)
            assert isinstance(low_level.package, PythonPackage)
            package = PythonPackageImpl(
                [
                    EntrypointImpl(name, target)
                    for name, target in low_level.package.entrypoints.items()
                ],
                low_level.package.dependencies,
            )
            pages = []
            ui_addons = []
            subscriptions = []
            async with api.critic.Query[Tuple[str, str, str]](
                critic,
                """SELECT name, description, entrypoint
                     FROM extensionendpointroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as endpoints_result:
                async for name, description, entrypoint in endpoints_result:
                    pages.append(EndpointImpl(description, entrypoint, name))
            async with api.critic.Query[Tuple[str, Optional[str], Optional[str]]](
                critic,
                """SELECT name, bundle_js, bundle_css
                     FROM extensionuiaddonroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as uiaddons_result:
                async for name, bundle_js, bundle_css in uiaddons_result:
                    ui_addons.append(UIAddonImpl(name, bundle_js, bundle_css))
            async with api.critic.Query[Tuple[str, bool, str, str]](
                critic,
                """SELECT channel, TRUE, description, entrypoint
                     FROM extensionsubscriptionroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as subscriptions_result:
                async for channel, reserved, description, entrypoint in subscriptions_result:
                    subscriptions.append(
                        SubscriptionImpl(description, entrypoint, channel, reserved)
                    )
            self.__manifest = ManifestImpl(
                package, pages, ui_addons, subscriptions, low_level
            )
        return self.__manifest


@ExtensionVersion.cached
async def fetch(
    critic: api.critic.Critic,
    version_id: Optional[int],
    extension: Optional[api.extension.Extension],
    name: Optional[str],
) -> WrapperType:
    if version_id is not None:
        condition = "id={version_id}"
    elif name is not None:
        condition = "extension={extension} AND name={name}"
    else:
        condition = "extension={extension} AND name IS NULL"
    async with ExtensionVersion.query(
        critic, [condition], version_id=version_id, extension=extension, name=name,
    ) as result:
        try:
            return await ExtensionVersion.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if name is not None:
                raise api.extensionversion.InvalidName(value=name)
            raise


async def fetchAll(
    critic: api.critic.Critic, extension: Optional[api.extension.Extension]
) -> Sequence[WrapperType]:
    conditions = ["current"]
    if extension:
        conditions.append("extension={extension}")
    async with ExtensionVersion.query(
        critic, conditions, extension=extension
    ) as result:
        return await ExtensionVersion.make(critic, result)
