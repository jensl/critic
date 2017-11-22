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

from typing import Sequence, Union

from critic import api
from critic import jsonapi

ExternalAccount = api.externalaccount.ExternalAccount


class ExternalAccounts(
    jsonapi.ResourceClass[ExternalAccount], api_module=api.externalaccount
):
    """External accounts used for authentication of Critic users."""

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: ExternalAccount
    ) -> jsonapi.JSONResult:
        """ExternalAccount {
             "id": integer, // the external accounts's id (Critic internal)
             "enabled": boolean, // true if usable for authentication
             "provider": {
               "identifier": string, // unique identifier
               "title": string, // provider title, or null
             },
             "account": {
               "id": string, // external account id (e.g. username)
               "url": string, // URL of the account's page, or null

               // The following are useful as default values when creating
               // a Critic account to connect to this external account.
               "username": string, // external account's username, or null
               "fullname": string, // external account's full name, or null
               "email": string, // external account's email address, or null
             },
             "user": integer, // id of connected Critic user, or null
           }"""

        user = await value.user

        # Require either administrator privileges or the user whose external
        # accounts are being accessed.
        if user is not None:
            api.PermissionDenied.raiseUnlessUser(parameters.critic, user)

        return {
            "id": value.id,
            "enabled": value.enabled,
            "provider": {
                "identifier": value.provider_name,
                "title": value.provider_title,
            },
            "account": {
                "id": value.account_id,
                "username": value.account_username,
                "fullname": value.account_fullname,
                "email": value.account_email,
                "url": value.account_url,
            },
            "user": user,
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> ExternalAccount:
        """Retrieve one (or more) external accounts.

           EXTERNAL_ACCOUNT_ID : id

           Retrieve an external account identified by its unique internal id."""

        critic = parameters.critic

        external_account = await api.externalaccount.fetch(
            critic, jsonapi.numeric_id(argument)
        )

        # Allow access by id (which can be guessed easily) only to administrator
        # users, or the user connected to the account in question, *or* to
        # temporary sesssions signed in using an unconnected external account
        # (such a session would be used to create a new Critic user to connect
        # to the account, typically.)
        if external_account != critic.external_account:
            user = await external_account.user
            if user:
                api.PermissionDenied.raiseUnlessUser(critic, user)
            else:
                api.PermissionDenied.raiseUnlessAdministrator(critic)

        return external_account

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[ExternalAccount, Sequence[ExternalAccount]]:
        """Retrieve all external accounts.

           user : USER : -

           Retrieve only external accounts connected to the specified user. If
           combined with |provider|, the behavior is the same as for single
           access: a single object or a 404 HTTP status is returned.

           provider : PROVIDER_NAME : string

           Retrieve only external accounts from the specified provider.

           account : ACCOUNT_ID : string

           Retrieve the external account with the specified account id. This
           must be combined with |provider|, and cannot be combined with |user|.
           When used, the behavior is the same as for single access: a single
           object or a 404 HTTP status is returned."""

        critic = parameters.critic

        user = await Users.deduce(parameters)
        provider_name = parameters.getQueryParameter("provider")
        account_id = parameters.getQueryParameter("account")

        if user is not None and account_id is not None:
            raise jsonapi.UsageError(
                "query parameters 'user' and 'account' cannot be combined"
            )
        if account_id is not None and provider_name is None:
            raise jsonapi.UsageError(
                "missing query parameter 'provider' "
                "(required when 'account' is used)"
            )

        # Require either administrator privileges or the user whose external
        # accounts are being accessed. If |user| is None, the former is checked.
        # Note that a user is not allowed to search for an account by provider
        # and account id, even if the search would result in an external account
        # connected to the user in question.
        api.PermissionDenied.raiseUnlessUser(critic, user)

        if provider_name is not None and (user is not None or account_id is not None):
            if user is not None:
                return await api.externalaccount.fetch(
                    critic, provider_name=provider_name, user=user
                )
            else:
                assert account_id is not None
                return await api.externalaccount.fetch(
                    critic, provider_name=provider_name, account_id=account_id
                )

        return await api.externalaccount.fetchAll(
            critic, user=user, provider_name=provider_name
        )


from .users import Users
