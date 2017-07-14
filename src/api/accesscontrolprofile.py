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

class AccessControlProfileError(api.APIError):
    """Base exception for all errors related to the AccessControlProfile
       class"""
    pass

class InvalidAccessControlProfileId(AccessControlProfileError):
    """Raised when an invalid access control profile id is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidAccessControlProfileId, self).__init__(
            "Invalid access control profile id: %d" % value)
        self.value = value

class AccessControlProfile(api.APIObject):
    """Representation of a an access control profile"""

    RULE_VALUES = frozenset(["allow", "deny"])

    def __int__(self):
        return self.id

    @property
    def id(self):
        """The profile's unique id"""
        return self._impl.id

    @property
    def title(self):
        """The profile's title, or None"""
        return self._impl.title

    @property
    def access_token(self):
        """The access token that owns this profile, or None"""
        return self._impl.getAccessToken(self.critic)

    class Category(object):
        """Representation of an access control category

           Each category is controlled by a rule ("allow" or "deny") and a list
           of exceptions (possibly empty).  The effective policy is the rule,
           unless an exception applies, in which case it's the opposite of the
           rule."""

        def __init__(self, rule, exceptions):
            self.rule = rule
            self.exceptions = exceptions

    class HTTPException(object):
        """Representation of an exception for the "http" category

           The exception consists of the HTTP request method and a regular
           expression that must match the entire request path."""

        REQUEST_METHODS = frozenset(["GET", "HEAD", "OPTIONS",
                                     "POST", "PUT", "DELETE"])

        def __init__(self, exception_id, request_method, path_pattern):
            self.id = exception_id
            self.request_method = request_method
            self.path_pattern = path_pattern

    @property
    def http(self):
        """Access control category "http"

           This category controls web frontend requests.

           Exceptions are of the type HTTPException."""
        return self._impl.getHTTP(self.critic)

    class RepositoryException(object):
        """Representation of an exception for the "repositories" category

           The exception consists of the access type ("read" or "modify") and the
           repository."""

        ACCESS_TYPES = frozenset(["read", "modify"])

        def __init__(self, exception_id, access_type, repository):
            self.id = exception_id
            self.access_type = access_type
            self.repository = repository

    @property
    def repositories(self):
        """Access control category "repositories"

           This category controls access to Git repositories, both via the web
           frontend and the Git hook.  Note that read-only Git access over SSH
           is not controlled by access control.

           Exceptions are of the type RepositoryException."""
        return self._impl.getRepositories(self.critic)

    class ExtensionException(object):
        """Representation of an exception for the "extensions" category

           The exception consists of the access type ("install" or "execute")
           and the extension."""

        ACCESS_TYPES = frozenset(["install", "execute"])

        def __init__(self, exception_id, access_type, extension):
            self.id = exception_id
            self.access_type = access_type
            self.extension = extension

    @property
    def extensions(self):
        """Access control category "extensions"

           This category controls access to any functionality provided by an
           extension.

           Exceptions are of the type ExtensionException."""
        return self._impl.getExtensions(self.critic)

def fetch(critic, profile_id):
    """Fetch an AccessControlProfile object with the given profile id"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.accesscontrolprofile.fetch(critic, int(profile_id))

def fetchAll(critic, title=None):
    """Fetch AccessControlProfile objects for all primary profiles in the system

       A profile is primary if it is not the additional restrictions imposed for
       accesses authenticated with an access token.

       If |title| is not None, fetch only profiles with a matching title."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    if title is not None:
        title = str(title)
    return api.impl.accesscontrolprofile.fetchAll(critic, title)
