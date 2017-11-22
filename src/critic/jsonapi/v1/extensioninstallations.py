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

from typing import Sequence

from critic import api
from critic import jsonapi

ExtensionInstallation = api.extensioninstallation.ExtensionInstallation


async def modify(
    transaction: api.transaction.Transaction, installation: ExtensionInstallation
) -> api.transaction.extensioninstallation.ModifyExtensionInstallation:
    user = await installation.user
    if user is None:
        return await transaction.modifyExtensionInstallation(installation)
    return await transaction.modifyUser(user).modifyExtensionInstallation(installation)


class ExtensionInstallations(
    jsonapi.ResourceClass[ExtensionInstallation], api_module=api.extensioninstallation
):
    """Extensions installations."""

    contexts = (None, "users", "extensions")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: ExtensionInstallation
    ) -> jsonapi.JSONResult:
        """ExtensionInstallation {
             "id": integer,
             "extension": integer,
             "version": integer or null,
             "user": integer or null,
           }"""

        async def manifest() -> jsonapi.JSONResult:
            version = await value.version
            manifest = await version.manifest
            if manifest is None:
                return None
            return {
                "ui_addons": [
                    {
                        "name": ui_addon.name,
                        "has_js": ui_addon.bundle_js is not None,
                        "has_css": ui_addon.bundle_css is not None,
                    }
                    for ui_addon in manifest.ui_addons
                ]
            }

        return {
            "id": value.id,
            "extension": value.extension,
            "version": value.version,
            "user": value.user,
            "manifest": manifest(),
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> ExtensionInstallation:
        """Retrieve one (or more) extension installations by id.

           INSTALLATION_ID : integer

           Retrieve an extension installation identified by its unique numeric
           id."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.PathError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        value = await api.extensioninstallation.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        if "users" in parameters.context:
            if await value.user != parameters.context["users"]:
                raise jsonapi.PathError(
                    "Extension installation does not " "belong to the specified user"
                )

        return value

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[ExtensionInstallation]:
        """Retrieve all extensions installations."""

        if not api.critic.settings().extensions.enabled:
            raise jsonapi.UsageError(
                "Extension support not enabled", code="NO_EXTENSIONS"
            )

        extension = await Extensions.deduce(parameters)
        version = None
        user = await Users.deduce(parameters)

        universal_parameter = parameters.getQueryParameter("universal")
        if universal_parameter is not None:
            if user is not None:
                raise jsonapi.UsageError(
                    "Conflicting query parameter: universal=%s when user is "
                    "also specified" % universal_parameter
                )
            user = api.user.anonymous(parameters.critic)

        version_parameter = parameters.getQueryParameter("version")
        if version_parameter is not None:
            if extension is None:
                raise jsonapi.UsageError(
                    "Invalid query parameter: version=%s when no extension has "
                    "been specified" % version_parameter
                )
            if version_parameter == "(live)":
                version_name = None
            else:
                version_name = version_parameter
            version = await api.extensionversion.fetch(
                parameters.critic, extension=extension, name=version_name
            )

        if version is not None:
            return await api.extensioninstallation.fetchAll(
                parameters.critic, version=version, user=user
            )
        elif extension is not None:
            return await api.extensioninstallation.fetchAll(
                parameters.critic, extension=extension, user=user
            )
        else:
            return await api.extensioninstallation.fetchAll(
                parameters.critic, user=user
            )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> ExtensionInstallation:
        converted = await jsonapi.convert(
            parameters,
            {
                "user?": api.user.User,
                "extension?": api.extension.Extension,
                "version?": api.extensionversion.ExtensionVersion,
                "universal?": bool,
            },
            data,
        )

        critic = parameters.critic

        user = converted.get(
            "user", parameters.context.get("users", critic.actual_user)
        )
        extension = converted.get("extension", parameters.context.get("extensions"))
        version = converted.get("version", parameters.context.get("extensionversions"))
        universal = converted.get("universal", False)

        if "user" in converted and universal:
            raise jsonapi.InputError("Only one of user and universal allowed")

        if universal:
            user = None

        if version:
            if extension and (await version.extension) != extension:
                raise jsonapi.InputError("Mismatch between extension and version")
            extension = await version.extension
        else:
            version = await api.extensionversion.fetch(
                critic, extension=extension, name=None
            )

        async with api.transaction.start(critic) as transaction:
            if user:
                modifier = await transaction.modifyUser(user).installExtension(
                    extension, version
                )
            else:
                modifier = await transaction.installExtension(extension, version)

        return await modifier

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[ExtensionInstallation],
        data: jsonapi.JSONInput,
    ) -> None:
        converted = await jsonapi.convert(
            parameters, {"version": api.extensionversion.ExtensionVersion}, data,
        )

        version = converted.get("version")

        if version is not None:
            for installation in values:
                if (await version.extension) != (await installation.extension):
                    raise jsonapi.UsageError(
                        "Cannot upgrade installation to version of a different "
                        "extension"
                    )

        async with api.transaction.start(parameters.critic) as transaction:
            for installation in values:
                await (await modify(transaction, installation)).upgradeTo(version)

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[ExtensionInstallation]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for installation in values:
                parameters.addLinked(await installation.extension)
                await (await modify(transaction, installation)).deleteInstallation()


from .extensions import Extensions
from .users import Users
