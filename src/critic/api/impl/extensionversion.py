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

from dataclasses import dataclass
from typing import Literal, Tuple, Optional, Sequence

from critic import api
from critic.api import extensionversion as public
from critic import extensions
from critic.extensions import getExtensionSnapshotPath
from critic.extensions.manifest.pythonpackage import PythonPackage
from critic.gitaccess import SHA1
from critic.background import extensiontasks
from . import apiobject


@dataclass
class EntrypointImpl:
    __name: str
    __target: str

    @property
    def name(self) -> str:
        return self.__name

    @property
    def target(self) -> str:
        return self.__target


@dataclass
class PythonPackageImpl:
    __entrypoints: Sequence[api.extensionversion.ExtensionVersion.Entrypoint]
    __dependencies: Sequence[str]

    @property
    def package_type(self) -> Literal["python"]:
        return "python"

    @property
    def entrypoints(
        self,
    ) -> Sequence[api.extensionversion.ExtensionVersion.Entrypoint]:
        return self.__entrypoints

    @property
    def dependencies(self) -> Sequence[str]:
        return self.__dependencies


@dataclass
class RoleImpl:
    __description: str

    @property
    def description(self) -> str:
        return self.__description


@dataclass
class ExecutesServerSide(RoleImpl):
    __entrypoint: Optional[str]

    @property
    def entrypoint(self) -> Optional[str]:
        return self.__entrypoint


@dataclass
class EndpointImpl(ExecutesServerSide):
    __name: str

    @property
    def name(self) -> str:
        return self.__name


@dataclass
class UIAddonImpl(RoleImpl):
    __name: str
    __bundle_js: Optional[str]
    __bundle_css: Optional[str]

    @property
    def name(self) -> str:
        return self.__name

    @property
    def bundle_js(self) -> Optional[str]:
        return self.__bundle_js

    @property
    def bundle_css(self) -> Optional[str]:
        return self.__bundle_css


@dataclass
class SubscriptionImpl(ExecutesServerSide):
    __channel: str
    __reserved: bool

    @property
    def channel(self) -> str:
        return self.__channel

    @property
    def reserved(self) -> bool:
        return self.__reserved


@dataclass
class ManifestImpl:
    __package: api.extensionversion.ExtensionVersion.PythonPackage
    __endpoints: Sequence[api.extensionversion.ExtensionVersion.Endpoint]
    __ui_addons: Sequence[api.extensionversion.ExtensionVersion.UIAddon]
    __subscriptions: Sequence[api.extensionversion.ExtensionVersion.Subscription]
    __low_level: extensions.extension.Manifest

    @property
    def package(self) -> api.extensionversion.ExtensionVersion.PythonPackage:
        return self.__package

    @property
    def endpoints(self) -> Sequence[api.extensionversion.ExtensionVersion.Endpoint]:
        return self.__endpoints

    @property
    def ui_addons(self) -> Sequence[api.extensionversion.ExtensionVersion.UIAddon]:
        return self.__ui_addons

    @property
    def subscriptions(
        self,
    ) -> Sequence[api.extensionversion.ExtensionVersion.Subscription]:
        return self.__subscriptions

    @property
    def low_level(self) -> extensions.extension.Manifest:
        return self.__low_level


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
            async with api.critic.Query[Tuple[str, str, Optional[str], Optional[str]]](
                critic,
                """SELECT name, description, bundle_js, bundle_css
                     FROM extensionuiaddonroles
                     JOIN extensionroles ON (role=id)
                    WHERE version={version_id}""",
                version_id=self.id,
            ) as uiaddons_result:
                async for name, description, bundle_js, bundle_css in uiaddons_result:
                    ui_addons.append(
                        UIAddonImpl(name, description, bundle_js, bundle_css)
                    )
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


@public.fetchImpl
@ExtensionVersion.cached
async def fetch(
    critic: api.critic.Critic,
    version_id: Optional[int],
    extension: Optional[api.extension.Extension],
    name: Optional[str],
    sha1: Optional[SHA1],
) -> WrapperType:
    if version_id is not None:
        condition = "id={version_id}"
    elif name is not None:
        condition = "extension={extension} AND name={name}"
    elif sha1 is not None:
        condition = "extension={extension} AND sha1={sha1}"
    else:
        condition = "extension={extension} AND name IS NULL"
    async with ExtensionVersion.query(
        critic,
        [condition],
        version_id=version_id,
        extension=extension,
        name=name,
        sha1=sha1,
    ) as result:
        try:
            return await ExtensionVersion.makeOne(critic, result)
        except result.ZeroRowsInResult:
            if name is not None:
                raise api.extensionversion.InvalidName(value=name)
            if sha1 is not None:
                raise api.extensionversion.InvalidSHA1(value=name)
            raise


@public.fetchAllImpl
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
