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
from typing import Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic.api.transaction.usersshkey.modify import ModifyUserSSHKey
from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


async def modify(
    transaction: api.transaction.Transaction, usersshkey: api.usersshkey.UserSSHKey
) -> ModifyUserSSHKey:
    return await transaction.modifyUser(await usersshkey.user).modifySSHKey(usersshkey)


class UserSSHKeys(ResourceClass[api.usersshkey.UserSSHKey], api_module=api.usersshkey):
    contexts = (None, "users")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.usersshkey.UserSSHKey
    ) -> JSONResult:
        return {
            "id": value.id,
            "user": value.user,
            "type": value.type,
            "key": value.key,
            "comment": value.comment,
            "bits": value.bits,
            "fingerprint": value.fingerprint,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.usersshkey.UserSSHKey:
        """Retrieve one (or more) SSH keys.

        KEY_ID : integer

        Retrieve an SSH key identified by its unique numeric id."""

        if not api.critic.settings().authentication.enable_ssh_access:
            raise UsageError("SSH access support is disabled")

        value = await api.usersshkey.fetch(parameters.critic, numeric_id(argument))

        if "users" in parameters.context:
            if await value.user != parameters.context["users"]:
                raise PathError("SSH key does not belong to specified user")

        return value

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.usersshkey.UserSSHKey]:
        """All SSH keys."""

        if not api.critic.settings().authentication.enable_ssh_access:
            raise UsageError("SSH access support is disabled")

        user = await parameters.deduce(api.user.User)

        return await api.usersshkey.fetchAll(parameters.critic, user=user)

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.usersshkey.UserSSHKey:
        converted = await convert(
            parameters,
            {"user?": api.user.User, "type": str, "key": str, "comment?": str},
            data,
        )

        critic = parameters.critic
        user = converted.get(
            "user", parameters.context.get("users", critic.actual_user)
        )

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.modifyUser(user).addSSHKey(
                    converted["type"], converted["key"], converted.get("comment")
                )
            ).subject

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[api.usersshkey.UserSSHKey],
        data: JSONInput,
    ) -> None:
        converted = await convert(parameters, {"comment": str}, data)
        comment = converted["comment"]

        async with api.transaction.start(parameters.critic) as transaction:
            for usersshkey in values:
                await (await modify(transaction, usersshkey)).setComment(comment)

    @classmethod
    async def delete(
        cls,
        parameters: Parameters,
        values: Values[api.usersshkey.UserSSHKey],
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for usersshkey in values:
                await (await modify(transaction, usersshkey)).delete()
