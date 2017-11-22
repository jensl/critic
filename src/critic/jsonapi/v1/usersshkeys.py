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
from typing import Optional, Sequence, Any, Awaitable

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


async def modify(
    transaction: api.transaction.Transaction, usersshkey: api.usersshkey.UserSSHKey
) -> api.transaction.usersshkey.ModifyUserSSHKey:
    return await transaction.modifyUser(await usersshkey.user).modifySSHKey(usersshkey)


class UserSSHKeys(jsonapi.ResourceClass, api_module=api.usersshkey):
    contexts = (None, "users")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.usersshkey.UserSSHKey
    ) -> jsonapi.JSONResult:
        return {
            "id": value.id,
            "user": value.user,
            "type": value.type,
            "key": value.key,
            "comment": value.comment,
            "bits": value.bits,
            "fingerprint": value.fingerprint,
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.usersshkey.UserSSHKey:
        """Retrieve one (or more) SSH keys.

           KEY_ID : integer

           Retrieve an SSH key identified by its unique numeric id."""

        if not api.critic.settings().authentication.enable_ssh_access:
            raise jsonapi.UsageError("SSH access support is disabled")

        value = await api.usersshkey.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        if "users" in parameters.context:
            if await value.user != parameters.context["users"]:
                raise jsonapi.PathError("SSH key does not belong to specified user")

        return value

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.usersshkey.UserSSHKey]:
        """All SSH keys."""

        if not api.critic.settings().authentication.enable_ssh_access:
            raise jsonapi.UsageError("SSH access support is disabled")

        user = await Users.deduce(parameters)

        return await api.usersshkey.fetchAll(parameters.critic, user=user)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.usersshkey.UserSSHKey:
        converted = await jsonapi.convert(
            parameters,
            {"user?": api.user.User, "type": str, "key": str, "comment?": str},
            data,
        )

        critic = parameters.critic
        user = converted.get(
            "user", parameters.context.get("users", critic.actual_user)
        )

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyUser(user).addSSHKey(
                converted["type"], converted["key"], converted.get("comment")
            )

        return await modifier

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.usersshkey.UserSSHKey],
        data: jsonapi.JSONInput,
    ) -> None:
        converted = await jsonapi.convert(parameters, {"comment": str}, data)
        comment = converted["comment"]

        async with api.transaction.start(parameters.critic) as transaction:
            for usersshkey in values:
                (await modify(transaction, usersshkey)).setComment(comment)

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[api.usersshkey.UserSSHKey],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for usersshkey in values:
                (await modify(transaction, usersshkey)).delete()


from .users import Users
