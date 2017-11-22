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
from typing import Optional, Sequence, Set, Union, Any

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class Users(jsonapi.ResourceClass[api.user.User], api_module=api.user):
    """The users of this system."""

    anonymous_create = True

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.user.User
    ) -> jsonapi.JSONResult:
        """User {
             "id": integer, // the user's id
             "name": string, // the user's unique user name
             "fullname": string, // the user's full name
             "status": string, // the user's status: "current", "absent",
                                  "retired" or "disabled"
             "email": string, // the user's primary email address
           }"""

        result: jsonapi.JSONResult = {
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

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> api.user.User:
        """Retrieve one (or more) users of this system.

           USER_ID : integer or "me"

           Retrieve a user identified by the user's unique numeric id, or the
           identifier "me" to retrieve the current user."""

        if argument == "me":
            user = parameters.critic.effective_user
            if user.is_anonymous:
                raise api.user.Error("'users/me' (not signed in)")
        else:
            user = await api.user.fetch(parameters.critic, jsonapi.numeric_id(argument))
        return user

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
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

        name_parameter = parameters.getQueryParameter("name")
        if name_parameter:
            return await api.user.fetch(parameters.critic, name=name_parameter)
        status = parameters.getQueryParameter(
            "status", converter=jsonapi.many(api.user.as_status)
        )
        sort_parameter = parameters.getQueryParameter(
            "sort", "id", choices={"id", "name", "fullname", "email"}
        )
        return sorted(
            await api.user.fetchAll(parameters.critic, status=status),
            key=lambda user: getattr(user, sort_parameter),
        )

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.user.User],
        data: jsonapi.JSONInput,
    ) -> None:
        if not isinstance(values, jsonapi.SingleValue):
            raise jsonapi.UsageError("Updating multiple users not supported")

        critic = parameters.critic
        user = values.get()

        converted = await jsonapi.convert(
            parameters,
            {"fullname?": str, "password?": {"current?": str, "new": str}},
            data,
        )

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyUser(user)

            if "fullname" in converted:
                new_fullname = converted["fullname"].strip()
                if not new_fullname:
                    raise jsonapi.InputError("Empty new fullname")
                modifier.setFullname(new_fullname)

            if "password" in converted:
                from critic import auth

                authdb = auth.Database.get()
                if not authdb.supportsPasswordChange():
                    raise jsonapi.UsageError("Password changes are not supported")
                password = converted["password"]
                current_pw = password.get("current")
                new_pw = password["new"]
                if not new_pw.strip():
                    raise jsonapi.InputError("Empty password not allowed")
                try:
                    await authdb.changePassword(critic, modifier, current_pw, new_pw)
                except auth.WrongPassword:
                    raise jsonapi.InputError("Wrong current password")

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.user.User:
        critic = parameters.critic

        converted = await jsonapi.convert(
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

        if password is not None:
            from critic import auth

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
                modifier.addRole(role)

        return await modifier

    @staticmethod
    async def deduce(parameters: jsonapi.Parameters) -> Optional[api.user.User]:
        user = parameters.context.get("users")
        user_parameter = parameters.getQueryParameter("user")
        if user_parameter is not None:
            if user is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: user=%s" % user_parameter
                )
            user = await Users.fromParameter(parameters, user_parameter)
        return user

    @staticmethod
    async def fromParameterValue(
        parameters: jsonapi.Parameters, value: str
    ) -> api.user.User:
        user_id, name = jsonapi.id_or_name(value)
        if user_id is not None:
            return await api.user.fetch(parameters.critic, user_id)
        assert name is not None
        if name == "(me)":
            return parameters.critic.effective_user
        if name == "(anonymous)":
            return api.user.anonymous(parameters.critic)
        return await api.user.fetch(parameters.critic, name=name)

    @staticmethod
    async def setAsContext(parameters: jsonapi.Parameters, user: api.user.User) -> None:
        parameters.setContext(Users.name, user)
