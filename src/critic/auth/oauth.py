# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

from critic import api
from critic import auth
from critic import dbaccess
from ..wsgi import request


class OAuthProvider(auth.Provider):
    async def start(self, req):
        state = auth.getToken()
        authorize_url = self.getAuthorizeURL(state)
        target_url = req.getParameter("target", None)

        critic = req.critic

        async with critic.transaction() as cursor:
            await cursor.execute(
                """INSERT
                     INTO oauthstates (state, url)
                   VALUES ({state}, {target_url})""",
                state=state,
                target_url=target_url,
            )

        raise request.Found(authorize_url)

    async def finish(self, req):
        import aiohttp

        if req.method != "GET":
            raise auth.InvalidRequest

        code = req.getParameter("code", default=None)
        state = req.getParameter("state", default=None)

        if code is None or state is None:
            raise auth.InvalidRequest("Missing parameter(s)")

        critic = req.critic

        async with critic.query(
            """SELECT url
                 FROM oauthstates
                WHERE state={state}""",
            state=state,
        ) as result:
            try:
                target_url = await result.scalar()
            except dbaccess.ZeroRowsInResult:
                raise auth.InvalidRequest("Invalid OAuth state: " + state)

        async with aiohttp.ClientSession() as session:
            access_token = await self.getAccessToken(session, code)
            if access_token is None:
                raise auth.Failure("failed to get access token")

            user_data = await self.getUserData(session, access_token)
            if user_data is None:
                raise auth.Failure("failed to get user data")

        account_id = user_data["account"]
        username = user_data["username"]
        fullname = user_data.get("fullname", username)
        email = user_data["email"]

        try:
            external_account = await api.externalaccount.fetch(
                critic, provider_name=self.name, account_id=account_id
            )
        except api.externalaccount.NotFound:
            created_external_account = api.transaction.CollectCreatedObject(
                api.externalaccount.ExternalAccount
            )

            async with api.transaction.start(critic) as transaction:
                transaction.createExternalAccount(
                    self.name,
                    account_id,
                    username=username,
                    fullname=fullname,
                    email=email,
                    callback=created_external_account,
                )

            external_account = await created_external_account
            user = None
        else:
            user = await external_account.user

        create_user = False

        if (
            user is None
            and auth.isValidUserName(username)
            and self.configuration.bypass_createuser
        ):
            try:
                await api.user.fetch(critic, name=username)
            except api.user.InvalidName:
                create_user = True

        if create_user:
            await critic.setExternalAccount(external_account)

            async with api.transaction.start(critic) as transaction:
                modifier = await transaction.createUser(
                    username, fullname, email, external_account=external_account
                )
                modifier.connectTo(external_account)

            user = await modifier.user

        await auth.createSessionId(req, user, external_account=external_account)

        raise request.Found(target_url or "/")
