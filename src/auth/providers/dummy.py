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

import hashlib
import urllib

import configuration
import auth

class DummyOAuthProvider(auth.OAuthProvider):
    """Dummy OAuth authentication provider used by automatic tests"""

    def __init__(self, name):
        super(DummyOAuthProvider, self).__init__(name)
        self.access_token = None

    def getTitle(self):
        """Title, suitable as X in 'Sign in using your X'"""
        return self.name.capitalize() + " account"

    def getAccountIdDescription(self):
        return self.name.capitalize() + " username"

    def getAccountURL(self, name):
        return "https://example.com/user/%s" % name

    def getAuthorizeURL(self, state):
        query = urllib.urlencode({ "state": state })
        return "https://example.com/authorize?%s" % query

    def getAccessToken(self, code):
        if code == "incorrect":
            raise auth.Failure("Incorrect code")
        self.access_token = hashlib.sha1(code).hexdigest()
        return self.access_token

    def getUserData(self, access_token):
        if access_token != self.access_token:
            raise auth.Failure("Invalid access token")
        return { "account": "account-" + self.name,
                 "username": self.name,
                 "email": self.name + "@example.org",
                 "fullname": self.name.capitalize() + " von Testing" }

if configuration.debug.IS_TESTING:
    def createProvider(name, allow_user_registration, verify_email_addresses,
                       bypass_createuser):
        configuration.auth.PROVIDERS[name] = {
            "enabled": True,
            "allow_user_registration": allow_user_registration,
            "verify_email_addresses": verify_email_addresses,
            "client_id": "DummyClientId",
            "client_secret": "DummyClientSecret",
            "bypass_createuser": bypass_createuser
        }
        auth.PROVIDERS[name] = DummyOAuthProvider(name)

    createProvider("alice", False, False, False)
    createProvider("carol", True, False, False)
    createProvider("felix", True, False, True)
    createProvider("gina", True, True, False)
