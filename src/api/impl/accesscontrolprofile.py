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
import apiobject
import dbutils

public_class = api.accesscontrolprofile.AccessControlProfile

HTTPException = public_class.HTTPException
RepositoryException = public_class.RepositoryException
ExtensionException = public_class.ExtensionException

class AccessControlProfile(apiobject.APIObject):
    wrapper_class = api.accesscontrolprofile.AccessControlProfile

    def __init__(self, profile_id, title, token_id, *rules):
        self.id = profile_id
        self.title = title
        self.__token_id = token_id
        (self.http_rule,
         self.repositories_rule,
         self.extensions_rule) = rules

    def getAccessToken(self, critic):
        if self.__token_id is None:
            return None
        return api.accesstoken.fetch(critic, self.__token_id)

    def getHTTP(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, request_method, path_pattern
                            FROM accesscontrol_http
                           WHERE profile=%s
                        ORDER BY id ASC""",
                       (self.id,))
        return public_class.Category(
            self.http_rule,
            [HTTPException(exception_id, request_method, path_pattern)
             for exception_id, request_method, path_pattern, in cursor])

    def getRepositories(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, access_type, repository
                            FROM accesscontrol_repositories
                           WHERE profile=%s
                        ORDER BY id ASC""",
                       (self.id,))
        return public_class.Category(
            self.repositories_rule,
            [RepositoryException(exception_id, access_type,
                                 api.repository.fetch(critic, repository_id)
                                 if repository_id is not None else None)
             for exception_id, access_type, repository_id in cursor])

    def getExtensions(self, critic):
        import configuration
        if not configuration.extensions.ENABLED:
            return public_class.Category(self.extensions_rule, [])
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, access_type, extension_key
                            FROM accesscontrol_extensions
                           WHERE profile=%s
                        ORDER BY id ASC""",
                       (self.id,))
        return public_class.Category(
            self.extensions_rule,
            [ExtensionException(exception_id, access_type,
                                api.extension.fetch(critic, key=extension_key)
                                if extension_key is not None else None)
             for exception_id, access_type, extension_key in cursor])

    def refresh(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, title, access_token, http, repositories,
                                 extensions
                            FROM accesscontrolprofiles
                           WHERE id=%s""",
                       (self.id,))
        for row in cursor:
            return AccessControlProfile(*row)
        return self

def fetch(critic, profile_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, title, access_token, http, repositories,
                             extensions
                        FROM accesscontrolprofiles
                       WHERE id=%s""",
                   (profile_id,))
    try:
        return next(AccessControlProfile.make(critic, cursor))
    except StopIteration:
        raise api.accesscontrolprofile.InvalidAccessControlProfileId(profile_id)

def fetchAll(critic, title):
    cursor = critic.getDatabaseCursor()
    if title is None:
        cursor.execute("""SELECT id, title, NULL, http, repositories, extensions
                            FROM accesscontrolprofiles
                           WHERE access_token IS NULL
                        ORDER BY id ASC""")
    else:
        cursor.execute("""SELECT id, title, NULL, http, repositories, extensions
                            FROM accesscontrolprofiles
                           WHERE access_token IS NULL
                             AND title=%s
                        ORDER BY id ASC""",
                       (title,))
    return list(AccessControlProfile.make(critic, cursor))
