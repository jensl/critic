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
from typing import Sequence, Optional, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi


class UserEmails(
    jsonapi.ResourceClass[api.useremail.UserEmail], api_module=api.useremail
):
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
        parameters: jsonapi.Parameters, value: api.useremail.UserEmail
    ) -> jsonapi.JSONResult:
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

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> api.useremail.UserEmail:
        """Retrieve one (or more) user email addresses.

           ADDRESS_ID : integer

           Retrieve an email address identified by its unique numeric id."""
        useremail = await api.useremail.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

        user = await Users.deduce(parameters)
        if user and user != await useremail.user:
            raise jsonapi.PathError("Email address does not belong to specified user")

        return useremail

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.useremail.UserEmail]:
        """All primary email addresses."""

        user = await Users.deduce(parameters)
        status = parameters.getQueryParameter(
            "status", converter=api.useremail.as_status
        )
        selected = parameters.getQueryParameter("selected", choices={"yes", "no"})

        return await api.useremail.fetchAll(
            parameters.critic, user=user, status=status, selected=selected == "yes"
        )

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.useremail.UserEmail:
        converted = await jsonapi.convert(
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
            modifier = transaction.modifyUser(user).addEmailAddress(
                converted["address"], **kwargs
            )

        return await modifier

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.useremail.UserEmail]
    ) -> None:
        async with api.transaction.start(parameters.critic) as transaction:
            for useremail in values:
                (
                    await transaction.modifyUser(
                        await useremail.user
                    ).modifyEmailAddress(useremail)
                ).delete()


from .users import Users
