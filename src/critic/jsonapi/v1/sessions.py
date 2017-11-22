# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2016 the Critic contributors, Opera Software ASA
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

from typing import Optional, Literal

from critic import api
from critic import jsonapi
from critic import auth

from ..exceptions import Error


class Session:
    id = "current"

    session_type: Optional[Literal["accesstoken", "normal"]]

    def __init__(self, critic: api.critic.Critic):
        self.user = critic.actual_user
        if critic.access_token:
            self.session_type = "accesstoken"
        elif critic.actual_user:
            self.session_type = "normal"
        else:
            self.session_type = None
        self.external_account = critic.external_account


class SessionError(Error):
    http_status = 403
    title = "Session error"

    def __init__(self, message: str, *, code: str = None):
        super().__init__(message)
        self.code = code


class Sessions(
    jsonapi.ResourceClass[Session], resource_name="sessions", value_class=Session
):
    """The session of the accessing client."""

    anonymous_create = True

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: Session
    ) -> jsonapi.JSONResult:
        """Session {
             "user": integer, // the signed in user's id, or null
             "type": "normal" or "accesstoken", or null,
             "fields": [
                 {
                     "identifier": string, // unique field identifier
                     "label": string,      // UI label
                     "hidden": boolean,    // true for passwords
                     "description": string or null
                 },
                 ...
             ],
             "providers": [
                {
                    "identifier": string,
                    // Title, suitable as X in "Sign in using your X".
                    "title": string,
                    // Account identifier label, i.e. a suitable label for
                    // a hypothetical input field for it.
                    "account_id_label": string
                },
                ...
             ],
           }"""

        fields = []
        for db_field in auth.Database.get().getFields():
            hidden, identifier, label = db_field[:3]
            if len(db_field) == 4:
                description = db_field[3]
            else:
                description = None
            fields.append(
                {
                    "identifier": identifier,
                    "label": label,
                    "hidden": hidden,
                    "description": description,
                }
            )

        providers = []
        for provider in auth.Provider.enabled().values():
            providers.append(
                {
                    "identifier": provider.name,
                    "title": provider.getTitle(),
                    "account_id_label": provider.getAccountIdDescription(),
                }
            )
        providers.sort(key=lambda provider: provider["identifier"])

        return {
            "user": value.user,
            "type": value.session_type,
            "external_account": value.external_account,
            "fields": fields,
            "providers": providers,
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> Session:
        """Retrieve the current session.

           CURRENT : "current"

           Retrieve the current session."""

        if argument != "current":
            raise jsonapi.UsageError('Resource argument must be "current"')

        return Session(parameters.critic)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> Session:
        fields = auth.Database.get().getFields()

        converted = await jsonapi.convert(
            parameters, {fieldname: str for hidden, fieldname, label in fields}, data
        )

        critic = parameters.critic

        if critic.actual_user:
            raise SessionError("session already created")

        try:
            await auth.Database.get().authenticate(critic, converted)
        except auth.AuthenticationFailed as error:
            raise SessionError(str(error), code=f"invalid:{error.field_name}")

        await auth.createSessionId(parameters.req, critic.actual_user)

        return Session(critic)

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[Session]
    ) -> None:
        await auth.deleteSessionId(parameters.req)
