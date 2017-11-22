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

logger = logging.getLogger(__name__)

from critic import api
from critic import auth


class AccessTokens(auth.Database):
    name = "accesstokens"

    def __init__(self, authdb):
        self.authdb = authdb

    def getFields(self):
        return self.authdb.getFields()

    async def authenticate(self, db, fields):
        await self.authdb.authenticate(db, fields)

    def getAuthenticationLabels(self, user):
        return self.authdb.getAuthenticationLabels(user)

    def supportsHTTPAuthentication(self):
        # HTTP authentication is the primary use-case.
        return True

    async def performHTTPAuthentication(self, critic, *, username, password, token):
        logger.debug(f"{username=} {password=} {token=}")
        if username is not None and password is not None:
            conditions = ["users.name={username}", "accesstokens.token={password}"]
        elif token is not None:
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
                    critic, username=username, password=username, token=None
                )
            raise auth.InvalidToken("Invalid token")

        access_token = await api.accesstoken.fetch(critic, token_id)

        authentication_labels = ()

        if access_token.access_type == "anonymous":
            user = None
        elif access_token.access_type == "system":
            user = api.user.system(critic)
        else:
            user = await access_token.user
            authentication_labels = self.getAuthenticationLabels(user)

        if user:
            await critic.setActualUser(user)

        await critic.setAccessToken(access_token)

        logger.debug(f"{critic.access_token=} {critic.actual_user=}")

        critic.setAuthenticationLabels(authentication_labels)

        profile = await access_token.profile

        if profile:
            critic.addAccessControlProfile(profile)

    def supportsPasswordChange(self):
        return self.authdb.supportsPasswordChange()

    async def changePassword(self, critic, *rest):
        if critic.access_token is not None:
            raise auth.AccessDenied
        return await self.authdb.changePassword(critic, *rest)
