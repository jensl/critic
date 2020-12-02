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
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api.transaction.accesstoken.modify import ModifyAccessToken

from critic.api.accesstoken import ACCESS_TYPES

from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values
from .accesscontrolprofiles import PROFILE, updateProfile


async def modifyAccessToken(
    transaction: api.transaction.Transaction, access_token: api.accesstoken.AccessToken
) -> ModifyAccessToken:
    user = await access_token.user
    if user:
        return await transaction.modifyUser(user).modifyAccessToken(access_token)
    return transaction.modifyAccessToken(access_token)


class AccessTokens(
    ResourceClass[api.accesstoken.AccessToken], api_module=api.accesstoken
):
    """Access tokens."""

    contexts = (None, "users")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.accesstoken.AccessToken
    ) -> JSONResult:
        """AccessToken {
          "id": integer,
          "access_type": "user", "anonymous" or "system",
          "user": integer or null,
          "token": string,
          "title": string or null,
          "profile": integer or null,
        }"""

        # Make sure that only administrator users can access other user's access
        # tokens or access tokens that do not belong to any user.
        if (
            value.access_type != "user"
            or parameters.critic.actual_user != await value.user
        ):
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        data: JSONResult = {
            "id": value.id,
            "access_type": value.access_type,
            "user": value.user,
            "title": value.title,
            "profile": value.profile,
        }

        token = parameters.context.get("AccessToken.token")
        if token is not None:
            data["token"] = token

        return data

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.accesstoken.AccessToken:
        """Retrieve one (or more) access tokens.

        TOKEN_ID : integer

        Retrieve an access token identified by its unique numeric id."""

        if not api.critic.settings().authentication.enable_access_tokens:
            raise UsageError("Access token support is disabled")

        value = await api.accesstoken.fetch(parameters.critic, numeric_id(argument))

        if "users" in parameters.context:
            if await value.user != parameters.context["users"]:
                raise PathError("Access token does not belong to specified user")

        return value

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.accesstoken.AccessToken]:
        """All access tokens."""

        if not api.critic.settings().authentication.enable_access_tokens:
            raise UsageError("Access token support is disabled")

        user = await parameters.deduce(api.user.User)

        # Only administrators are allowed to access all access tokens in the
        # system.
        if user is None:
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        return await api.accesstoken.fetchAll(parameters.critic, user=user)

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.accesstoken.AccessToken:
        critic = parameters.critic

        user = parameters.in_context(api.user.User, critic.actual_user)
        assert user

        converted = await convert(
            parameters,
            {"access_type?": ACCESS_TYPES, "title?": str, "profile?": PROFILE},
            data,
        )

        access_type = converted.get("access_type", "user")

        async with api.transaction.start(critic) as transaction:
            if access_type == "user":
                modifier, token_value = await transaction.modifyUser(
                    user
                ).createAccessToken(converted.get("title"))
            else:
                modifier, token_value = await transaction.createAccessToken(
                    access_type, converted.get("title")
                )

            if "profile" in converted:
                await updateProfile(
                    await modifier.modifyProfile(), converted["profile"]
                )

            parameters.context["AccessToken.token"] = token_value

            return modifier.subject

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.accesstoken.AccessToken],
        data: JSONInput,
    ) -> None:
        critic = parameters.critic

        converted = await convert(
            parameters, {"title?": str, "profile?": PROFILE}, data
        )

        async with api.transaction.start(critic) as transaction:
            for access_token in values:
                modifier = await modifyAccessToken(transaction, access_token)

                if "title" in converted:
                    await modifier.setTitle(converted["title"])

                if "profile" in converted:
                    await updateProfile(
                        await modifier.modifyProfile(), converted["profile"]
                    )

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[api.accesstoken.AccessToken],
    ) -> None:
        critic = parameters.critic

        async with api.transaction.start(critic) as transaction:
            for access_token in values:
                modifier = await modifyAccessToken(transaction, access_token)
                await modifier.delete()

    @classmethod
    async def deduce(
        cls, parameters: Parameters
    ) -> Optional[api.accesstoken.AccessToken]:
        return parameters.in_context(api.accesstoken.AccessToken)


from .users import Users
