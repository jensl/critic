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

import api

class AccessTokenError(api.APIError):
    """Base exception for all errors related to the AccessToken class"""
    pass

class InvalidAccessTokenId(AccessTokenError):
    """Raised when an invalid access token id is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidAccessTokenId, self).__init__(
            "Invalid access token id: %d" % value)
        self.value = value

class AccessToken(api.APIObject):
    """Representation of an access token"""

    def __int__(self):
        return self.id
    def __hash__(self):
        return hash(int(self))
    def __eq__(self, other):
        return int(self) == int(other)

    @property
    def access_type(self):
        """The type of access granted by this access token"""
        return self._impl.access_type

    @property
    def id(self):
        """The access token's unique id"""
        return self._impl.id

    @property
    def user(self):
        """The user authenticated by the access token, or None"""
        return self._impl.getUser(self.critic)

    @property
    def part1(self):
        """The first part of the access token"""
        return self._impl.part1

    @property
    def part2(self):
        """The second part of the access token"""
        return self._impl.part2

    @property
    def title(self):
        """The access token's title, or None"""
        return self._impl.title

    @property
    def profile(self):
        """The access token's access control profile"""
        return self._impl.getProfile(self.critic)

def fetch(critic, token_id):
    """Fetch an AccessToken object with the given token id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.accesstoken.fetch(critic, int(token_id))

def fetchAll(critic, user=None):
    """Fetch AccessToken objects for all primary profiles in the system

       A profile is primary if it is not the additional restrictions imposed for
       accesses authenticated with an access token.

       If |user| is not None, return only access tokens belonging to the
       specified user."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert user is None or isinstance(user, api.user.User)
    return api.impl.accesstoken.fetchAll(critic, user)
