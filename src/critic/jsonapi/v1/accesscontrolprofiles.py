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
from typing import Dict, Mapping, Any, Sequence, Type, Iterable, Union, Optional

logger = logging.getLogger(__name__)

from critic import api
from critic.api.transaction import accesscontrolprofile as transaction_acp
from critic.api.accesscontrolprofile import (
    RULE_VALUES,
    HTTP_METHODS,
    REPOSITORY_ACCESS_TYPES,
    EXTENSION_ACCESS_TYPES,
)

from ..check import RegularExpression, convert
from ..exceptions import UsageError, PathError
from ..parameters import Parameters
from ..resourceclass import ResourceClass
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


CATEGORIES = frozenset(["http", "repositories", "extensions"])

HTTP_EXCEPTION = {
    "request_method=null": HTTP_METHODS,
    "path_pattern=null": RegularExpression,
}
REPOSITORIES_EXCEPTION = {
    "access_type=null": REPOSITORY_ACCESS_TYPES,
    "repository=null": api.repository.Repository,
}
EXTENSION_EXCEPTION = {
    "access_type=null": EXTENSION_ACCESS_TYPES,
    "extension=null": api.extension.Extension,
}

PROFILE: Dict[str, Any] = {
    "http?": {"rule": RULE_VALUES, "exceptions?": [HTTP_EXCEPTION]},
    "repositories?": {"rule": RULE_VALUES, "exceptions?": [REPOSITORIES_EXCEPTION]},
    "extensions?": {"rule": RULE_VALUES, "exceptions?": [EXTENSION_EXCEPTION]},
}

PROFILE_WITH_TITLE = PROFILE.copy()
PROFILE_WITH_TITLE["title?"] = str


def updateProfile(
    profile_modifier: transaction_acp.ModifyAccessControlProfile,
    converted: Mapping[str, Any],
) -> None:
    def updateExceptions(
        exceptions_modifier: transaction_acp.ModifyExceptions,
        exceptions: Iterable[Mapping[str, Any]],
    ) -> None:
        exceptions_modifier.deleteAll()
        for exception in exceptions:
            exceptions_modifier.add(**exception)

    def updateCategory(category: api.accesscontrolprofile.CategoryType) -> None:
        if category not in converted:
            return
        if "rule" in converted[category]:
            profile_modifier.setRule(category, converted[category]["rule"])
        if "exceptions" in converted[category]:
            exceptions_modifier: transaction_acp.ModifyExceptions
            if category == "http":
                exceptions_modifier = profile_modifier.modifyHTTPExceptions()
            elif category == "repositories":
                exceptions_modifier = profile_modifier.modifyRepositoriesExceptions()
            else:
                exceptions_modifier = profile_modifier.modifyExtensionsExceptions()
            updateExceptions(exceptions_modifier, converted[category]["exceptions"])

    if "title" in converted:
        profile_modifier.setTitle(converted["title"])

    updateCategory("http")
    updateCategory("repositories")
    updateCategory("extensions")


ACP = api.accesscontrolprofile.AccessControlProfile


class AccessControlProfiles(ResourceClass[ACP], api_module=api.accesscontrolprofile):
    """The access control profiles of this system."""

    contexts = (None, "accesstokens:profile")

    @staticmethod
    async def json(parameters: Parameters, value: ACP) -> JSONResult:
        """AccessControlProfile {
             "id": integer,
             "title": string or null,
             "http": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "request_method": string or null,
                 "path_pattern": string or null
               }]
             },
             "repositories": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "access_type": "read" or "modify",
                 "repository": integer
               }]
             },
             "extensions": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "access_type": "install" or "execute",
                 "extension": string,
               }]
             }
           }"""

        token = await value.access_token

        # Make sure that only administrator users can access profiles that are
        # not connected to access tokens, and that only administrator users and
        # the user that owns the access token can access other profiles.
        if (
            not token
            or token.access_type != "user"
            or parameters.critic.actual_user != await token.user
        ):
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        async def http_category() -> JSONResult:
            category = await value.http
            return {
                "rule": category.rule,
                "exceptions": [
                    {
                        "id": exception.id,
                        "request_method": exception.request_method,
                        "path_pattern": exception.path_pattern,
                    }
                    for exception in category.exceptions
                ],
            }

        async def repositories_category() -> JSONResult:
            category = await value.repositories
            return {
                "rule": category.rule,
                "exceptions": [
                    {
                        "id": exception.id,
                        "access_type": exception.access_type,
                        "repository": exception.repository,
                    }
                    for exception in category.exceptions
                ],
            }

        async def extensions_category() -> JSONResult:
            category = await value.extensions
            return {
                "rule": category.rule,
                "exceptions": [
                    {
                        "id": exception.id,
                        "access_type": exception.access_type,
                        "extension": exception.extension,
                    }
                    for exception in category.exceptions
                ],
            }

        return {
            "id": value.id,
            "title": value.title,
            "http": http_category(),
            "repositories": repositories_category(),
            "extensions": extensions_category(),
        }

    @staticmethod
    async def single(parameters: Parameters, argument: str) -> ACP:
        """Retrieve one (or more) access control profiles.

           PROFILE_ID : integer

           Retrieve an access control profile identified by the profile's unique
           numeric id."""

        return await api.accesscontrolprofile.fetch(
            parameters.critic, numeric_id(argument)
        )

    @staticmethod
    async def multiple(parameters: Parameters) -> Union[ACP, Sequence[ACP]]:
        """Retrieve all primary access control profiles in the system.

           title : TITLE : string

           Retrieve only access control profiles with a matching title."""
        token = await AccessTokens.deduce(parameters)
        if token:
            profile = await token.profile
            if profile is None:
                raise PathError("Access token has no associated profile")
            return profile
        title_parameter = parameters.getQueryParameter("title")
        return await api.accesscontrolprofile.fetchAll(
            parameters.critic, title=title_parameter
        )

    @staticmethod
    async def deduce(parameters: Parameters) -> Optional[ACP]:
        profile = parameters.context.get("accesscontrolprofiles")
        profile_parameter = parameters.getQueryParameter("profile")
        if profile_parameter is not None:
            if profile is not None:
                raise UsageError(
                    "Redundant query parameter: profile=%s" % profile_parameter
                )
            profile_id = numeric_id(profile_parameter)
            profile = await api.accesscontrolprofile.fetch(
                parameters.critic, profile_id
            )
        return profile

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> ACP:
        critic = parameters.critic
        converted = await convert(parameters, PROFILE_WITH_TITLE, data)

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.createAccessControlProfile()
            updateProfile(modifier, converted)

        return await modifier

    @staticmethod
    async def update(
        parameters: Parameters, values: Values[ACP], data: JSONInput,
    ) -> None:
        converted = await convert(parameters, PROFILE_WITH_TITLE, data)

        async with api.transaction.start(parameters.critic) as transaction:
            for profile in values:
                modifier = transaction.modifyAccessControlProfile(profile)
                updateProfile(modifier, converted)

    @staticmethod
    async def delete(parameters: Parameters, values: Values[ACP]) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for profile in values:
                transaction.modifyAccessControlProfile(profile).delete()


from .accesstokens import AccessTokens
