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

import re

import base
import auth
import configuration

class AccessDenied(Exception):
    """Raised by AccessControl checks on failure"""
    pass

class AccessControlError(Exception):
    """Raised in case of system configuration errors"""
    pass

class HTTPException(object):
    def __init__(self, request_method, path_pattern):
        self.request_method = request_method
        self.path_regexp = (re.compile("^" + path_pattern + "$")
                            if path_pattern is not None else None)

    def applies(self, req):
        if self.request_method is not None \
                and self.request_method != req.method:
            return False
        if self.path_regexp is not None \
                and not self.path_regexp.match(req.path):
            return False
        return True

class RepositoryException(object):
    def __init__(self, access_type, repository_id):
        self.access_type = access_type
        self.repository_id = repository_id

    def applies(self, access_type, repository_id):
        if self.access_type is not None \
                and self.access_type != access_type:
            return False
        if self.repository_id is not None \
                and self.repository_id != repository_id:
            return False
        return True

class ExtensionException(object):
    def __init__(self, access_type, extension_key):
        self.access_type = access_type
        self.extension_key = extension_key

    def applies(self, access_type, extension):
        if self.access_type is not None \
                and self.access_type != access_type:
            return False
        if self.extension_key is not None \
                and self.extension_key != extension.getKey():
            return False
        return True

def _isAllowed(rule, exceptions, *args):
    # If an exception applies, then allow if the rule is "deny" ...
    if any(exception.applies(*args) for exception in exceptions):
        return rule == "deny"
    # ... otherwise allow if the rule is "allow".
    return rule == "allow"

class AccessControlProfile(object):
    def __init__(self, *rules):
        if len(rules) == 1:
            rules = rules * 3

        (self.http_rule,
         self.repositories_rule,
         self.extensions_rule) = rules

        self.http_exceptions = []
        self.repositories_exceptions = []
        self.extensions_exceptions = []

    @staticmethod
    def isAllowedHTTP(profiles, req):
        return all(_isAllowed(profile.http_rule, profile.http_exceptions, req)
                   for profile in profiles)

    @staticmethod
    def isAllowedRepository(profiles, access_type, repository_id):
        return all(_isAllowed(profile.repositories_rule,
                              profile.repositories_exceptions,
                              access_type, repository_id)
                   for profile in profiles)

    @staticmethod
    def isAllowedExtension(profiles, access_type, extension):
        return all(_isAllowed(profile.extensions_rule,
                              profile.extensions_exceptions,
                              access_type, extension)
                   for profile in profiles)

    @staticmethod
    def forUser(db, user, authentication_labels=()):
        cursor = db.readonly_cursor()
        if user.isSystem():
            # The system user can always do everything.
            return AccessControlProfile("allow")
        if user.isAnonymous():
            if not configuration.base.ALLOW_ANONYMOUS_USER:
                profile = AccessControlProfile("deny")
                if configuration.base.SESSION_TYPE == "cookie":
                    # Hard-coded exceptions to allow access to things that must
                    # be accessed in order for the user to load the login page
                    # and successfully sign in.
                    profile.http_exceptions.extend([
                        HTTPException("GET", "login"),
                        HTTPException("POST", "validatelogin")
                    ])
                return profile
            cursor.execute("""SELECT profile
                                FROM useraccesscontrolprofiles
                               WHERE access_type='anonymous'""")
            row = cursor.fetchone()
        else:
            cursor.execute("""SELECT profile
                                FROM useraccesscontrolprofiles
                               WHERE access_type='user'
                                 AND uid=%s""",
                           (user.id,))
            row = cursor.fetchone()
            if not row and authentication_labels:
                cursor.execute("""SELECT profile
                                    FROM labeledaccesscontrolprofiles
                                   WHERE labels=%s""",
                               ("|".join(sorted(authentication_labels)),))
                row = cursor.fetchone()
        if not row:
            cursor.execute("""SELECT profile
                                FROM useraccesscontrolprofiles
                               WHERE access_type='user'
                                 AND uid IS NULL""")
            row = cursor.fetchone()
        if not row:
            # By default, allow everything.
            return AccessControlProfile("allow")
        profile_id, = row
        return AccessControlProfile.fromId(db, profile_id)

    @staticmethod
    def fromId(db, profile_id):
        cursor = db.readonly_cursor()
        cursor.execute(
            """SELECT http, repositories, extensions
                 FROM accesscontrolprofiles
                WHERE id=%s""",
            (profile_id,))

        profile = AccessControlProfile(*cursor.fetchone())

        cursor.execute("""SELECT request_method, path_pattern
                            FROM accesscontrol_http
                           WHERE profile=%s""",
                       (profile_id,))
        profile.http_exceptions.extend(
            HTTPException(request_method, path_pattern)
            for request_method, path_pattern in cursor)

        cursor.execute("""SELECT access_type, repository
                            FROM accesscontrol_repositories
                           WHERE profile=%s""",
                       (profile_id,))
        profile.repositories_exceptions.extend(
            RepositoryException(access_type, repository_id)
            for access_type, repository_id in cursor)

        if configuration.extensions.ENABLED:
            cursor.execute("""SELECT access_type, extension_key
                                FROM accesscontrol_extensions
                               WHERE profile=%s""",
                           (profile_id,))
            profile.extensions_exceptions.extend(
                ExtensionException(access_type, extension_key)
                for access_type, extension_key in cursor)

        return profile

class AccessControl(object):
    @staticmethod
    def forRequest(db, req):
        # Check the session status of the request.  This raises exceptions in
        # various situations.  If no exception is raised, req.user will have
        # been set, possibly to the anonymous user (or the system user.)
        auth.checkSession(db, req)

        assert db.user
        assert db.profiles

    @staticmethod
    def accessHTTP(db, req):
        if not AccessControlProfile.isAllowedHTTP(db.profiles, req):
            raise AccessDenied("Access denied: %s /%s" % (req.method, req.path))

    @staticmethod
    def accessRepository(db, access_type, repository):
        if not AccessControlProfile.isAllowedRepository(
                db.profiles, access_type, repository.id):
            raise AccessDenied("Repository access denied: %s %s"
                               % (access_type, repository.path))

    @staticmethod
    def accessExtension(db, access_type, extension):
        if not AccessControlProfile.isAllowedExtension(
                db.profiles, access_type, extension):
            raise AccessDenied("Access denied to extension: %s %s"
                               % (access_type, extension.getKey()))
