# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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
from typing import Sequence, TypedDict, Union, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic.background.extensiontasks import read_manifest
from critic.gitaccess import as_sha1

from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from .extensions import modify_extension

ExtensionVersion = api.extensionversion.ExtensionVersion


class Author(TypedDict):
    name: str
    email: Optional[str]


class ExtensionVersions(
    ResourceClass[ExtensionVersion], api_module=api.extensionversion
):
    """Extension versoins."""

    contexts = (None, "extensions")

    @staticmethod
    async def json(parameters: Parameters, value: ExtensionVersion) -> JSONResult:
        async def description() -> str:
            return (await value.manifest).description

        async def authors() -> Sequence[Author]:
            result: list[Author] = []
            for author in (await value.manifest).authors:
                result.append({"name": author.name, "email": author.email})
            return result

        return {
            "id": value.id,
            "extension": value.extension,
            "name": value.name,
            "sha1": value.sha1,
            "description": description(),
            "authors": authors(),
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> ExtensionVersion:
        """Retrieve one (or more) extension versions by id.

        VERSION_ID : integer

        Retrieve an extension version identified by its unique numeric id."""

        if not api.critic.settings().extensions.enabled:
            raise PathError("Extension support not enabled", code="NO_EXTENSIONS")

        return await api.extensionversion.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[ExtensionVersion, Sequence[ExtensionVersion]]:
        """Retrieve all extension versions."""

        if not api.critic.settings().extensions.enabled:
            raise UsageError("Extension support not enabled", code="NO_EXTENSIONS")

        extension = await parameters.deduce(api.extension.Extension)
        if not extension:
            raise UsageError.missingParameter("extension")

        name_parameter = parameters.query.get("name")
        if name_parameter is not None:
            return await api.extensionversion.fetch(
                parameters.critic, extension=extension, name=name_parameter
            )

        return await api.extensionversion.fetchAll(
            parameters.critic, extension=extension
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.extensionversion.ExtensionVersion:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {"extension?": api.extension.Extension, "name": str, "sha1": str},
            data,
        )

        extension = await parameters.deduce(api.extension.Extension)

        if not extension:
            if "extension" not in converted:
                raise UsageError("No extension specified")
            extension = converted["extension"]
        elif "extension" in converted and extension != converted["extension"]:
            raise UsageError("Conflicting extensions specified")
        assert extension is not None

        name = converted["name"]
        sha1 = as_sha1(converted["sha1"])
        manifest = await read_manifest(extension=extension, sha1=sha1)

        async with api.transaction.start(critic) as transaction:
            modifier = await modify_extension(transaction, extension)
            return (await modifier.createExtensionVersion(name, sha1, manifest)).subject

    @classmethod
    async def deduce(
        cls,
        parameters: Parameters,
    ) -> Optional[ExtensionVersion]:
        version = parameters.in_context(api.extensionversion.ExtensionVersion)
        version_parameter = parameters.query.get("version")
        if version_parameter is not None:
            if version is not None:
                raise UsageError.redundantParameter("version")
            version = await ExtensionVersions.fromParameterValue(
                parameters, version_parameter
            )
        return version

    @classmethod
    async def setAsContext(
        cls, parameters: Parameters, version: ExtensionVersion, /
    ) -> None:
        await super().setAsContext(parameters, version)

        # Also set the version's extension as context.
        await Extensions.setAsContext(parameters, await version.extension)

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.extensionversion.ExtensionVersion:
        logger.debug(f"fromParameterValue: {numeric_id(value)=}")
        return await api.extensionversion.fetch(parameters.critic, numeric_id(value))


from .extensions import Extensions
