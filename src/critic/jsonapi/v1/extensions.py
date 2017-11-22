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
from typing import Sequence, Union, Protocol, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class ExtensionManager(Protocol):
    async def createExtension(
        self, name: str, uri: str
    ) -> api.transaction.extension.ModifyExtension:
        ...

    async def modifyExtension(
        self, extension: api.extension.Extension
    ) -> api.transaction.extension.ModifyExtension:
        ...


def extension_manager(
    transaction: api.transaction.Transaction, publisher: Optional[api.user.User]
) -> ExtensionManager:
    if publisher and publisher.is_regular:
        return transaction.modifyUser(publisher)
    return transaction


class Extensions(
    jsonapi.ResourceClass[api.extension.Extension], api_module=api.extension
):
    """Extensions."""

    contexts = (None, "users")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.extension.Extension
    ) -> jsonapi.JSONResult:
        """Extension {
             "id": integer,
             "name": string,
             "key": string,
             "publisher": integer or null,
             "versions": integer[],
             "installation": integer or null,
           }"""

        return {
            "id": value.id,
            "name": value.name,
            "key": value.key,
            "publisher": value.publisher,
            "uri": value.uri,
            "versions": value.versions,
            "installation": value.installation,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.extension.Extension:
        """Retrieve one (or more) extensions by id.

           EXTENSION_ID : integer

           Retrieve an extension identified by its unique numeric id."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.PathError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        value = await api.extension.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        if "users" in parameters.context:
            if await value.publisher != parameters.context["users"]:
                raise jsonapi.PathError(
                    "Extension is not published by the specified user"
                )

        return value

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.extension.Extension, Sequence[api.extension.Extension]]:
        """Retrieve a single extension by key or all extensions.

           key : KEY : string

           Retrieve only the extension with the given key.  This is equivalent
           to accessing /api/v1/extensions/EXTENSION_ID with that extension's
           numeric id.  When used, other parameters are ignored.

           installed_by : INSTALLED_BY : integer or string

           Retrieve only extensions installed by the specified user.  The user
           can be identified by numeric id or username."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.UsageError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        key_parameter = parameters.getQueryParameter("key")
        if key_parameter:
            return await api.extension.fetch(parameters.critic, key=key_parameter)

        installed_by = await Users.fromParameter(parameters, "installed_by")

        return await api.extension.fetchAll(
            parameters.critic,
            publisher=await Users.deduce(parameters),
            installed_by=installed_by,
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.extension.Extension:
        converted = await jsonapi.convert(
            parameters,
            {"name": str, "publisher?": api.user.User, "system?": bool, "uri": str},
            data,
        )

        critic = parameters.critic

        name: str = converted["name"]
        publisher: Optional[api.user.User] = converted.get("publisher")
        system: bool = converted.get("system", False)
        uri: str = converted["uri"]

        if system:
            if publisher:
                raise jsonapi.UsageError.invalidInput(
                    data, "publisher", details="must be omitted for system extension"
                )
        elif publisher is None:
            publisher = critic.effective_user

        async with api.transaction.start(critic) as transaction:
            modifier = await extension_manager(transaction, publisher).createExtension(
                name, uri
            )

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.extension.Extension]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for extension in values:
                modifier = await extension_manager(
                    transaction, await extension.publisher
                ).modifyExtension(extension)
                await modifier.deleteExtension()

    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters,
    ) -> Optional[api.extension.Extension]:
        extension = parameters.context.get("extensions")
        extension_parameter = parameters.getQueryParameter("extension")
        if extension_parameter is not None:
            if extension is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: extension=%s" % extension_parameter
                )
            extension = await Extensions.fromParameter(parameters, extension_parameter)
        return extension

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.extension.Extension:
        return await api.extension.fetch(parameters.critic, key=value)

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, extension: api.extension.Extension
    ) -> None:
        parameters.setContext(Extensions.name, extension)


from .users import Users
