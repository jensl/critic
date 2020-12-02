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
from ..check import convert
from ..exceptions import PathError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id
from ..values import Values


class UserEmails(ResourceClass[api.useremail.UserEmail], api_module=api.useremail):
    """A user's primary email addresses.

    A "primary" email address is one that Critic would send emails to.  A
    user can have multiple primary email addresses registered, but at most
    one of them can be selected.  Emails are only sent to a selected primary
    email address.

    A user also has a set of "Git" email addresses.  Those are only compared
    against Git commit meta-data, and are never used when sending emails."""

    contexts = ("users", None)

    @staticmethod
    async def json(
        parameters: Parameters, value: api.useremail.UserEmail
    ) -> JSONResult:
        """Email {
          "id": int,              // the address's unique id
          "user": int,            // owning user's id
          "address": string,      // the email address
          "is_selected": boolean, // true if address is selected
          "status": "verified", "trusted" or "unverified"
        }"""

        return {
            "id": value.id,
            "user": value.user,
            "address": value.address,
            "is_selected": value.is_selected,
            "status": value.status,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.useremail.UserEmail:
        """Retrieve one (or more) user email addresses.

        ADDRESS_ID : integer

        Retrieve an email address identified by its unique numeric id."""
        useremail = await api.useremail.fetch(parameters.critic, numeric_id(argument))

        user = await parameters.deduce(api.user.User)
        if user and user != await useremail.user:
            raise PathError("Email address does not belong to specified user")

        return useremail

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.useremail.UserEmail]:
        """All primary email addresses."""

        user = await parameters.deduce(api.user.User)
        status = parameters.query.get("status", converter=api.useremail.as_status)
        selected = parameters.query.get("selected", choices={"yes", "no"})

        return await api.useremail.fetchAll(
            parameters.critic, user=user, status=status, selected=selected == "yes"
        )

    @staticmethod
    async def create(
        parameters: Parameters, data: JSONInput
    ) -> api.useremail.UserEmail:
        converted = await convert(
            parameters,
            {
                "user?": api.user.User,
                "address": str,
                "status?": api.useremail.STATUS_VALUES,
            },
            data,
        )

        critic = parameters.critic
        user = converted.get(
            "user", parameters.context.get("users", critic.actual_user)
        )

        kwargs = {}
        if "status" in converted:
            api.PermissionDenied.raiseUnlessAdministrator(critic)
            kwargs["status"] = converted["status"]

        async with api.transaction.start(critic) as transaction:
            return (
                await transaction.modifyUser(user).addEmailAddress(
                    converted["address"], **kwargs
                )
            ).subject

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.useremail.UserEmail]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for useremail in values:
                modifier = await transaction.modifyUser(
                    await useremail.user
                ).modifyEmailAddress(useremail)
                await modifier.delete()
