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

from typing import Sequence, Union, Optional

from critic import api
from critic import jsonapi

ExtensionVersion = api.extensionversion.ExtensionVersion


class ExtensionVersions(
    jsonapi.ResourceClass[ExtensionVersion], api_module=api.extensionversion
):
    """Extension versoins."""

    contexts = (None, "extensions")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: ExtensionVersion
    ) -> jsonapi.JSONResult:
        """Extension {
             "id": integer,
             "extension": integer,
             "name": string,
             "sha1": string,
           }"""

        return {
            "id": value.id,
            "extension": value.extension,
            "name": value.name,
            "sha1": value.sha1,
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> ExtensionVersion:
        """Retrieve one (or more) extension versions by id.

           VERSION_ID : integer

           Retrieve an extension version identified by its unique numeric id."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.PathError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        return await api.extensionversion.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[ExtensionVersion, Sequence[ExtensionVersion]]:
        """Retrieve all extension versions."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.UsageError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        extension = await Extensions.deduce(parameters)
        if not extension:
            raise jsonapi.UsageError.missingParameter("extension")

        name_parameter = parameters.getQueryParameter("name")
        if name_parameter is not None:
            return await api.extensionversion.fetch(
                parameters.critic, extension=extension, name=name_parameter
            )

        return await api.extensionversion.fetchAll(
            parameters.critic, extension=extension
        )

    @staticmethod
    async def deduce(parameters: jsonapi.Parameters,) -> Optional[ExtensionVersion]:
        return parameters.context.get("extensionversions")

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, version: ExtensionVersion
    ) -> None:
        parameters.setContext(ExtensionVersions.name, version)

        # Also set the version's extension as context.
        Extensions.setAsContext(parameters, await version.extension)


from .extensions import Extensions
