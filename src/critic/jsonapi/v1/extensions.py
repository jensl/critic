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
from critic.api.transaction.extension.modify import ModifyExtension
from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class ExtensionManager(Protocol):
    async def createExtension(self, name: str, url: str) -> ModifyExtension:
        ...

    async def modifyExtension(
        self, extension: api.extension.Extension
    ) -> ModifyExtension:
        ...


def extension_manager(
    transaction: api.transaction.Transaction, publisher: Optional[api.user.User]
) -> ExtensionManager:
    if publisher and publisher.is_regular:
        return transaction.modifyUser(publisher)
    return transaction


async def modify_extension(
    transaction: api.transaction.Transaction, extension: api.extension.Extension
) -> ModifyExtension:
    publisher = await extension.publisher
    if publisher:
        return await transaction.modifyUser(publisher).modifyExtension(extension)
    return await transaction.modifyExtension(extension)


class Extensions(ResourceClass[api.extension.Extension], api_module=api.extension):
    """Extensions."""

    contexts = (None, "users")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.extension.Extension
    ) -> JSONResult:
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
            "url": value.url,
            "versions": value.versions,
            "default_version": value.default_version,
            "installation": value.installation,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.extension.Extension:
        """Retrieve one (or more) extensions by id.

        EXTENSION_ID : integer

        Retrieve an extension identified by its unique numeric id."""

        if not api.critic.settings().extensions.enabled:
            raise PathError("Extension support not enabled", code="NO_EXTENSIONS")

        value = await api.extension.fetch(parameters.critic, numeric_id(argument))

        if "users" in parameters.context:
            if await value.publisher != parameters.context["users"]:
                raise PathError("Extension is not published by the specified user")

        return value

    @staticmethod
    async def multiple(
        parameters: Parameters,
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
            raise UsageError("Extension support not enabled", code="NO_EXTENSIONS")

        key_parameter = parameters.query.get("key")
        if key_parameter:
            return await api.extension.fetch(parameters.critic, key=key_parameter)

        installed_by = await parameters.fromParameter(api.user.User, "installed_by")

        return await api.extension.fetchAll(
            parameters.critic,
            publisher=await parameters.deduce(api.user.User),
            installed_by=installed_by,
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.extension.Extension:
        converted = await convert(
            parameters,
            {"name": str, "publisher?": api.user.User, "system?": bool, "url": str},
            data,
        )

        critic = parameters.critic

        name: str = converted["name"]
        publisher: Optional[api.user.User] = converted.get("publisher")
        system: bool = converted.get("system", False)
        url: str = converted["url"]

        if system:
            if publisher:
                raise UsageError.invalidInput(
                    data, "publisher", details="must be omitted for system extension"
                )
        elif publisher is None:
            publisher = critic.effective_user

        async with api.transaction.start(critic) as transaction:
            return (
                await extension_manager(transaction, publisher).createExtension(
                    name, url
                )
            ).subject

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.extension.Extension]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for extension in values:
                modifier = await extension_manager(
                    transaction, await extension.publisher
                ).modifyExtension(extension)
                await modifier.deleteExtension()

    @classmethod
    async def deduce(
        cls,
        parameters: Parameters,
    ) -> Optional[api.extension.Extension]:
        extension = parameters.in_context(api.extension.Extension)
        extension_parameter = parameters.query.get("extension")
        if extension_parameter is not None:
            if extension is not None:
                raise UsageError(
                    "Redundant query parameter: extension=%s" % extension_parameter
                )
            extension = await Extensions.fromParameterValue(
                parameters, extension_parameter
            )
        return extension

    @staticmethod
    async def fromParameterValue(
        parameters: Parameters, value: str
    ) -> api.extension.Extension:
        return await api.extension.fetch(parameters.critic, key=value)
