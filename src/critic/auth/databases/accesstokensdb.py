# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import logging
from typing import Collection, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import auth


class AccessTokens(auth.Database, dbname="accesstokens"):
    def __init__(self, authdb: auth.Database):
        self.authdb = authdb

    def getFields(self) -> Sequence[auth.database.Field]:
        return self.authdb.getFields()

    async def authenticate(
        self, critic: api.critic.Critic, fields: Mapping[str, str]
    ) -> api.user.User:
        return await self.authdb.authenticate(critic, fields)

    async def getAuthenticationLabels(self, user: api.user.User) -> Collection[str]:
        return await self.authdb.getAuthenticationLabels(user)

    def supportsHTTPAuthentication(self):
        # HTTP authentication is the primary use-case.
        return True

    async def performHTTPAuthentication(
        self,
        critic: api.critic.Critic,
        *,
        username: Optional[str],
        password: Optional[str],
        token: Optional[str],
    ) -> api.user.User:
        if username is not None and password is not None:
            conditions = ["users.name={username}", "accesstokens.token={password}"]
        else:
            assert token is not None
            conditions = ["accesstokens.token={token}"]

        async with api.critic.Query[int](
            critic,
            f"""SELECT accesstokens.id
                  FROM accesstokens
       LEFT OUTER JOIN users ON (
                         users.id=accesstokens.uid
                       )
                 WHERE {' AND '.join(conditions)}""",
            username=username,
            password=password,
            token=token,
        ) as result:
            token_id = await result.maybe_scalar()

        if token_id is None:
            logger.debug("no access token found")
            if username is not None and password is not None:
                return await self.authdb.performHTTPAuthentication(
                    critic, username=username, password=password, token=None
                )
            raise auth.InvalidToken("Invalid token")

        access_token = await api.accesstoken.fetch(critic, token_id)

        authentication_labels: Collection[str] = ()

        user = await access_token.user
        if user is None:
            if access_token.access_type == "anonymous":
                user = api.user.anonymous(critic)
            else:
                assert access_token.access_type == "system"
                user = api.user.system(critic)
        authentication_labels = await self.getAuthenticationLabels(user)

        if not user.is_anonymous:
            await critic.setActualUser(user)

        await critic.setAccessToken(access_token)

        critic.setAuthenticationLabels(authentication_labels)

        profile = await access_token.profile

        if profile:
            critic.addAccessControlProfile(profile)

        return user

    def supportsPasswordChange(self):
        return self.authdb.supportsPasswordChange()

    async def changePassword(
        self,
        critic: api.critic.Critic,
        user: api.user.User,
        modifier: auth.database.Modifier,
        current_pw: str,
        new_pw: str,
    ):
        if critic.access_token is not None:
            raise auth.AccessDenied
        return await self.authdb.changePassword(
            critic, user, modifier, current_pw, new_pw
        )
