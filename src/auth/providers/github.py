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

class GitHubAuthentication(auth.OAuthProvider):
    def __init__(self):
        super(GitHubAuthentication, self).__init__("github")

        self.client_id = self.configuration["client_id"]
        self.client_secret = self.configuration["client_secret"]
        self.redirect_uri = self.configuration["redirect_uri"]

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        return "GitHub account"

    def getAccountIdDescription(self):
        return "GitHub username"

    def getAccountURL(self, name):
        return "https://github.com/%s" % name

    def getAuthorizeURL(self, state):
        query = urllib.parse.urlencode({ "client_id": self.client_id,
                                   "redirect_uri": self.redirect_uri,
                                   "state": state })

        return "https://github.com/login/oauth/authorize?%s" % query

    def getAccessToken(self, code):
        response = urlutils.post(
            "https://github.com/login/oauth/access_token",
            data={ "client_id": self.client_id,
                   "client_secret": self.client_secret,
                   "code": code },
            headers={ "Accept": "application/json" })

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
            "https://api.github.com/user?access_token=%s" % access_token)

        if response.status_code != 200:
            return None

        data = response.json()

        if data is None or "login" not in data:
            return None

        return { "account": data["login"],
                 "username": data["login"],
                 "email": data.get("email"),
                 "fullname": data.get("name") }

if "github" in configuration.auth.PROVIDERS:
    if configuration.auth.PROVIDERS["github"]["enabled"]:
        auth.PROVIDERS["github"] = GitHubAuthentication()
