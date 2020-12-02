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

import aiohttp
import hashlib
import urllib.parse
from typing import Mapping, Optional

from critic import auth


class DummyOAuthProvider(auth.OAuthProvider):
    """Dummy OAuth authentication provider used by automatic tests"""

    access_token: Optional[str]

    def __init__(self, name: str):
        self.__name = name
        self.access_token = None

    @property
    def name(self) -> str:
        return self.__name

    def getTitle(self) -> str:
        """Title, suitable as X in 'Sign in using your X'"""
        return self.name.capitalize() + " account"

    def getAccountIdDescription(self) -> str:
        return self.name.capitalize() + " username"

    def getAccountURL(self, account_id: str) -> str:
        return "https://example.com/user/%s" % account_id

    def getAuthorizeURL(self, state: str) -> str:
        query = urllib.parse.urlencode({"state": state})
        return "https://example.com/authorize?%s" % query

    async def getAccessToken(self, session: aiohttp.ClientSession, code: str) -> str:
        if code == "incorrect":
            raise auth.Failure("Incorrect code")
        self.access_token = hashlib.sha1(code.encode()).hexdigest()
        return self.access_token

    async def getUserData(
        self, session: aiohttp.ClientSession, access_token: str
    ) -> Mapping[str, str]:
        if access_token != self.access_token:
            raise auth.Failure("Invalid access token")
        return {
            "account": "account-" + self.name,
            "username": self.name,
            "email": self.name + "@example.org",
            "fullname": self.name.capitalize() + " von Testing",
        }


# if configuration.debug.IS_TESTING:
#     def createProvider(name, allow_user_registration, verify_email_addresses,
#                        bypass_createuser):
#         configuration.auth.PROVIDERS[name] = {
#             "enabled": True,
#             "allow_user_registration": allow_user_registration,
#             "verify_email_addresses": verify_email_addresses,
#             "client_id": "DummyClientId",
#             "client_secret": "DummyClientSecret",
#             "bypass_createuser": bypass_createuser
#         }
#         auth.PROVIDERS[name] = DummyOAuthProvider(name)

#     createProvider("alice", False, False, False)
#     createProvider("carol", True, False, False)
#     createProvider("felix", True, False, True)
#     createProvider("gina", True, True, False)
