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

import logging

logger = logging.getLogger(__name__)

from critic import auth


class GitHubAuthentication(auth.OAuthProvider):
    name = "github"

    def __init__(self):
        self.client_id = self.configuration["client_id"]
        self.client_secret = self.configuration["client_secret"]
        self.redirect_uri = self.configuration["redirect_uri"]

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        return "GitHub account"

    def getAccountIdDescription(self):
        return "GitHub username"

    def getAccountURL(self, account_id):
        return "https://github.com/%s" % account_id

    def getAuthorizeURL(self, state):
        import urllib

        query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return "https://github.com/login/oauth/authorize?%s" % query

    async def getAccessToken(self, session, code):
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
        }

        async with session.post(
            "https://github.com/login/oauth/access_token", json=data
        ) as response:
            if response.status != 200:
                logger.warning(
                    "Fetching access token failed:\n  %d %s\n  %r",
                    response.status,
                    response.reason,
                    await response.text(),
                )
                return None
            data = await response.json()

        if data is None:
            return None
        if "error" in data:
            raise auth.Failure(data["error"])
        if "access_token" not in data:
            logger.warning("No `access_token` field in returned data: %r", data)
            return None

        return data["access_token"]

    async def getUserData(self, session, access_token):
        async with session.get(
            "https://api.github.com/user", params={"access_token": access_token}
        ) as response:
            if response.status != 200:
                logger.warning(
                    "Fetching user data failed:\n  %d %s\n  %r",
                    response.status,
                    response.reason,
                    await response.text(),
                )
                return None
            data = await response.json()

        if data is None:
            return None
        if "login" not in data:
            logger.warning("No `login` field in returned data: %r", data)
            return None

        return {
            "account": data["login"],
            "username": data["login"],
            "email": data.get("email"),
            "fullname": data.get("name"),
        }
