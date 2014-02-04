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

import urllib

import urlutils
import configuration
import auth

class GoogleAuthentication(auth.OAuthProvider):
    def __init__(self):
        super(GoogleAuthentication, self).__init__("google")

        self.client_id = self.configuration["client_id"]
        self.client_secret = self.configuration["client_secret"]
        self.redirect_uri = self.configuration["redirect_uri"]

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        return "Google account"

    def getAccountIdDescription(self):
        return "Google (e.g. GMail) email address"

    def getAccountURL(self, name):
        return None

    def getAuthorizeURL(self, state):
        query = urllib.urlencode({ "client_id": self.client_id,
                                   "response_type": "code",
                                   "scope": "openid email",
                                   "redirect_uri": self.redirect_uri,
                                   "state": state })

        return "https://accounts.google.com/o/oauth2/auth?" + query

    def getAccessToken(self, code):
        response = urlutils.post(
            "https://accounts.google.com/o/oauth2/token",
            data={ "code": code,
                   "client_id": self.client_id,
                   "client_secret": self.client_secret,
                   "redirect_uri": self.redirect_uri,
                   "grant_type": "authorization_code" },
            headers={ "Accept": "application/json" },
            verify=False)

        if response.status_code != 200:
            return None

        data = response.json()

        if data is None:
            return None
        elif "error" in data:
            raise auth.Failure(data["error"])
        elif "access_token" not in data:
            return None

        return data["access_token"]

    def getUserData(self, access_token):
        response = urlutils.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            params={ "access_token": access_token },
            verify=False)

        if response.status_code != 200:
            return None

        data = response.json()

        if data is None or "email" not in data:
            return None

        email = data["email"]
        username = email.partition("@")[0]

        return { "account": email,
                 "username": username,
                 "email": email,
                 "fullname": data.get("name", username) }

if "google" in configuration.auth.PROVIDERS:
    if configuration.auth.PROVIDERS["google"]["enabled"]:
        auth.PROVIDERS["google"] = GoogleAuthentication()
