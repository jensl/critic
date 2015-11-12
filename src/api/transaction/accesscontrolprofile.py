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

class InvalidRuleValue(api.TransactionError):
    pass

class InvalidRequestMethod(api.TransactionError):
    pass

class InvalidPathPattern(api.TransactionError):
    pass

class InvalidRepositoryAccessType(api.TransactionError):
    pass

class InvalidExtensionAccessType(api.TransactionError):
    pass

class ModifyExceptions(object):
    def __init__(self, transaction, profile):
        self.transaction = transaction
        self.profile = profile

    def __addTable(self):
        self.transaction.tables.add("accesscontrol_" + self.table_name)

    def delete(self, exception_id):
        self.__addTable()
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM accesscontrol_{}
                    WHERE id=%s
                      AND profile=%s""".format(self.table_name),
                (exception_id, self.profile.id)))

    def deleteAll(self):
        self.__addTable()
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM accesscontrol_{}
                    WHERE profile=%s""".format(self.table_name),
                (self.profile.id,)))

    def add(self, *values):
        self.__addTable()
        self.transaction.items.append(
            api.transaction.Query(
                """INSERT INTO accesscontrol_{} (profile, {})
                        VALUES (%s, {})""".format(
                            self.table_name,
                            ", ".join(self.column_names),
                            ", ".join(["%s"] * len(self.column_names))),
                (self.profile.id,) + values))

class ModifyHTTPExceptions(ModifyExceptions):
    table_name = "http"
    column_names = ("request_method", "path_pattern")

    def add(self, request_method, path_pattern):
        REQUEST_METHODS = api.accesscontrolprofile \
                .AccessControlProfile.HTTPException.REQUEST_METHODS

        if request_method is not None:
            if request_method not in REQUEST_METHODS:
                raise InvalidRequestMethod(request_method)

        if path_pattern is not None:
            import re
            try:
                re.compile(path_pattern)
            except re.error as error:
                raise InvalidPathPattern(
                    "%r: %s" % (path_pattern, error.message))

        super(ModifyHTTPExceptions, self).add(request_method, path_pattern)

class ModifyRepositoriesExceptions(ModifyExceptions):
    table_name = "repositories"
    column_names = ("access_type", "repository")

    def add(self, access_type, repository):
        assert (repository is None or
                isinstance(repository, api.repository.Repository))

        if access_type not in (None, "read", "modify"):
            raise InvalidRepositoryAccessType(access_type)

        repository_id = repository.id if repository else None

        super(ModifyRepositoriesExceptions, self).add(
            access_type, repository_id)

class ModifyExtensionsExceptions(ModifyExceptions):
    table_name = "extensions"
    column_names = ("access_type", "extension_key")

    def add(self, access_type, extension):
        assert (extension is None or
                isinstance(extension, api.extension.Extension))

        if access_type not in (None, "install", "execute"):
            raise InvalidExtensionAccessType(access_type)

        extension_key = extension.key if extension else None

        super(ModifyExtensionsExceptions, self).add(
            access_type, extension_key)

class ModifyAccessControlProfile(object):
    def __init__(self, transaction, profile):
        self.transaction = transaction
        self.profile = profile

    def setTitle(self, value):
        self.transaction.tables.add("accesscontrolprofiles")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE accesscontrolprofiles
                      SET title=%s
                    WHERE id=%s""",
                (value, self.profile.id)))

    def setRule(self, category, value):
        assert category in ("http", "repositories", "extensions")
        if value not in ("allow", "deny"):
            raise InvalidRuleValue(value)

        self.transaction.tables.add("accesscontrolprofiles")
        self.transaction.items.append(
            api.transaction.Query(
                """UPDATE accesscontrolprofiles
                      SET {}=%s
                    WHERE id=%s""".format(category),
                (value, self.profile.id)))

    def modifyExceptions(self, category):
        assert category in ("http", "repositories", "extensions")
        if category == "http":
            return ModifyHTTPExceptions(self.transaction, self.profile)
        if category == "repositories":
            return ModifyRepositoriesExceptions(self.transaction, self.profile)
        # category == "extensions"
        return ModifyExtensionsExceptions(self.transaction, self.profile)

    def delete(self):
        self.transaction.tables.add("accesscontrolprofiles")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM accesscontrolprofiles
                    WHERE id=%s""",
                (self.profile.id,)))

    @staticmethod
    def create(transaction, callback=None):
        critic = transaction.critic

        profile = CreatedAccessControlProfile(critic, None, callback)

        transaction.tables.add("accesscontrolprofiles")
        transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO accesscontrolprofiles
                  DEFAULT VALUES
                RETURNING id""",
                (),
                collector=profile))

        return ModifyAccessControlProfile(transaction, profile)

class CreatedAccessControlProfile(api.transaction.LazyAPIObject):
    def __init__(self, critic, access_token, callback=None):
        super(CreatedAccessControlProfile, self).__init__(
            critic, api.accesscontrolprofile.fetch, callback)
        self.access_token = access_token
