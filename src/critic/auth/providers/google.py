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

import re

from critic import auth


class GoogleAuthentication(auth.OAuthProvider):
    name = "google"

    def __init__(self):
        self.client_id = self.configuration.client_id
        self.client_secret = self.configuration.client_secret
        self.redirect_uri = self.configuration.redirect_uri
        self.required_domain = re.compile(self.configuration.required_domain)

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        return "Google account"

    def getAccountIdDescription(self):
        return "Google (e.g. GMail) email address"

    def getAuthorizeURL(self, state):
        import urllib

        query = urllib.parse.urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "openid email",
                "access_type": "online",
                "response_type": "code",
                "state": state,
            }
        )
        return "https://accounts.google.com/o/oauth2/v2/auth?" + query

    async def getAccessToken(self, session, code):
        query = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Accept": "application/json"}

        async with session.post(
            "https://www.googleapis.com/oauth2/v4/token", params=query, headers=headers
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()

        if data is None:
            return None
        elif "error" in data:
            raise auth.Failure(data["error"])
        elif "access_token" not in data:
            return None

        return data["access_token"]

    async def getUserData(self, session, access_token):
        async with session.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            params={"access_token": access_token},
        ) as response:
            if response.status != 200:
                return None
            data = await response.json()

        if data is None or "email" not in data:
            return None

        email = data["email"]
        username, _, domain = email.partition("@")

        match = self.required_domain.match(domain)
        if not match or match.group() != domain:
            return auth.Failure("access denied")

        return {
            "account": email,
            "username": username,
            "email": email,
            "fullname": data.get("name", username),
        }
