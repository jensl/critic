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

import aiohttp.web
import logging
from typing import Optional, Literal

logger = logging.getLogger(__name__)

from critic import api
from critic.api.apiobject import Actual
from critic import auth
from ..exceptions import Error
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..values import Values


class Session(api.APIObject):
    session_type: Optional[Literal["accesstoken", "normal"]]

    def __init__(self, critic: api.critic.Critic):
        self.__critic = critic
        self.user = critic.actual_user
        if critic.access_token:
            self.session_type = "accesstoken"
        elif critic.actual_user:
            self.session_type = "normal"
        else:
            self.session_type = None
        self.external_account = critic.external_account

    @property
    def critic(self) -> api.critic.Critic:
        return self.__critic

    @property
    def id(self) -> Literal["current"]:
        return "current"

    async def refresh(self: Actual) -> Actual:
        return self


class SessionError(Error):
    http_exception_type = aiohttp.web.HTTPForbidden
    title = "Session error"

    def __init__(self, message: str, *, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class Sessions(ResourceClass[Session], resource_name="sessions", value_class=Session):
    """The session of the accessing client."""

    anonymous_create = True

    @staticmethod
    async def json(parameters: Parameters, value: Session) -> JSONResult:
        """Session {
          "user": integer, // the signed in user's id, or null
          "session_type": "normal" or "accesstoken", or null,
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

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> Session:
        """Retrieve the current session.

        CURRENT : "current"

        Retrieve the current session."""

        if argument != "current":
            raise UsageError('Resource argument must be "current"')

        return Session(parameters.critic)

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> Session:
        fields = auth.Database.get().getFields()

        logger.debug(f"{fields=} {data=}")

        converted = await convert(
            parameters,
            {field.identifier: str for field in fields},
            data,
        )

        critic = parameters.critic

        if critic.actual_user:
            raise SessionError("session already created")

        try:
            user = await auth.Database.get().authenticate(critic, converted)
        except auth.AuthenticationFailed as error:
            raise SessionError(str(error), code=f"invalid:{error.field_name}")

        await auth.createSessionId(parameters.cookies, user)

        return Session(critic)

    @classmethod
    async def delete(cls, parameters: Parameters, values: Values[Session]) -> None:
        request = parameters.request
        assert isinstance(request, aiohttp.web.BaseRequest)
        await auth.deleteSessionId(request, parameters.cookies)
