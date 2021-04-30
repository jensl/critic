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

import logging
from typing import Optional, Sequence, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import auth
from ..check import convert
from ..exceptions import InputError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import id_or_name, many, numeric_id
from ..values import Values


class Users(ResourceClass[api.user.User], api_module=api.user):
    """The users of this system."""

    anonymous_create = True

    @staticmethod
    async def json(parameters: Parameters, value: api.user.User) -> JSONResult:
        """User {
          "id": integer, // the user's id
          "name": string, // the user's unique user name
          "fullname": string, // the user's full name
          "status": string, // the user's status: "current", "absent",
                               "retired" or "disabled"
          "email": string, // the user's primary email address
        }"""

        result: JSONResult = {
            "id": value.id,
            "name": value.name,
            "fullname": value.fullname,
            "status": value.status,
        }
        if parameters.critic.actual_user == value or parameters.critic.hasRole(
            "administrator"
        ):
            result["email"] = value.email
            result["roles"] = sorted(value.roles)
            result["password_status"] = value.password_status
        return result

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.user.User:
        """Retrieve one (or more) users of this system.

        USER_ID : integer or "me"

        Retrieve a user identified by the user's unique numeric id, or the
        identifier "me" to retrieve the current user."""

        if argument == "me":
            user = parameters.critic.effective_user
            if user.is_anonymous:
                raise api.user.Error("'users/me' (not signed in)")
        else:
            user = await api.user.fetch(parameters.critic, numeric_id(argument))
        return user

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Union[api.user.User, Sequence[api.user.User]]:
        """Retrieve a single named user or all users of this system.

        name : NAME : string

        Retrieve only the user with the given name.  This is equivalent to
        accessing /api/v1/users/USER_ID with that user's numeric id.  When
        used, any other parameters are ignored.

        status : USER_STATUS[,USER_STATUS,...] : string

        Include only users whose status is one of the specified.  Valid
        values are: <code>current</code>, <code>absent</code>,
        <code>retired</code> and <code>disabled</code>.

        sort : SORT_KEY : string

        Sort the returned users by the specified key.  Valid values are:
        <code>id</code>, <code>name</code>, <code>fullname</code>,
        <code>email</code>."""

        name_parameter = parameters.query.get("name")
        if name_parameter:
            return await api.user.fetch(parameters.critic, name=name_parameter)
        status = parameters.query.get("status", converter=many(api.user.as_status))
        sort_parameter = parameters.query.get(
            "sort", "id", choices={"id", "name", "fullname", "email"}
        )
        return sorted(
            await api.user.fetchAll(parameters.critic, status=status),
            key=lambda user: getattr(user, sort_parameter),
        )

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.user.User],
        data: JSONInput,
    ) -> None:
        if not values.is_single:
            raise UsageError("Updating multiple users not supported")

        critic = parameters.critic
        user = values.get()

        converted = await convert(
            parameters,
            {"fullname?": str, "password?": {"current?": str, "new": str}},
            data,
        )

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyUser(user)

            if "fullname" in converted:
                new_fullname = converted["fullname"].strip()
                if not new_fullname:
                    raise InputError("Empty new fullname")
                await modifier.setFullname(new_fullname)

            if "password" in converted:
                from critic import auth

                authdb = auth.Database.get()
                if not authdb.supportsPasswordChange():
                    raise UsageError("Password changes are not supported")
                password = converted["password"]
                current_pw = password.get("current")
                new_pw = password["new"]
                if not new_pw.strip():
                    raise InputError("Empty password not allowed")
                try:
                    await authdb.changePassword(
                        critic, user, modifier, current_pw, new_pw
                    )
                except auth.WrongPassword:
                    raise InputError("Wrong current password")

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.user.User:
        critic = parameters.critic

        converted = await convert(
            parameters,
            {
                "name": str,
                "fullname?": str,
                "email?": str,
                "password?": str,
                "roles?": [str],
            },
            data,
        )

        name = converted["name"]
        fullname = converted.get("fullname", name)
        email = converted.get("email")
        password = converted.get("password")
        roles = converted.get("roles", [])
        external_account = critic.external_account

        hashed_password: Optional[str]
        if password is not None:
            hashed_password = await auth.hashPassword(critic, password)
        else:
            hashed_password = None

        async with api.transaction.start(critic) as transaction:
            modifier = await transaction.createUser(
                name,
                fullname,
                email,
                hashed_password=hashed_password,
                external_account=external_account,
            )

            for role in roles:
                await modifier.addRole(role)

            user = modifier.subject

        return user

    @classmethod
    async def deduce(cls, parameters: Parameters) -> Optional[api.user.User]:
        user = parameters.in_context(api.user.User)
        user_parameter = parameters.query.get("user")
        if user_parameter is not None:
            if user is not None:
                raise UsageError("Redundant query parameter: user=%s" % user_parameter)
            user = await Users.fromParameterValue(parameters, user_parameter)
        return user

    @staticmethod
    async def fromParameterValue(parameters: Parameters, value: str) -> api.user.User:
        user_id, name = id_or_name(value)
        if user_id is not None:
            return await api.user.fetch(parameters.critic, user_id)
        assert name is not None
        if name == "(me)":
            return parameters.critic.effective_user
        if name == "(anonymous)":
            return api.user.anonymous(parameters.critic)
        return await api.user.fetch(parameters.critic, name=name)
