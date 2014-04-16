# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import dbutils
import gitutils
import reviewing.filters

from operation import (Operation, OperationResult, OperationFailure,
                       OperationError, Optional, typechecker)
from extensions.installation import (installExtension, uninstallExtension,
                                     reinstallExtension, InstallationError,
                                     getExtension)
from extensions.extension import Extension, ExtensionError
from extensions.manifest import FilterHookRole

class ExtensionOperation(Operation):
    def __init__(self, perform):
        Operation.__init__(self, { "extension_name": str,
                                   "author_name": Optional(str),
                                   "version": Optional(str),
                                   "universal": Optional(bool) })
        self.perform = perform

    def process(self, db, user, extension_name, author_name=None, version=None,
                universal=False):
        if universal:
            if not user.hasRole(db, "administrator"):
                raise OperationFailure(code="notallowed",
                                       title="Not allowed!",
                                       message="Operation not permitted.")
            user = None

        if version is not None:
            if version == "live":
                version = None
            elif version.startswith("version/"):
                version = version[8:]
            else:
                raise OperationError(
                    "invalid version, got '%s', expected 'live' or 'version/*'"
                    % version)

        try:
            self.perform(db, user, author_name, extension_name, version)
        except InstallationError as error:
            raise OperationFailure(code="installationerror",
                                   title=error.title,
                                   message=error.message,
                                   is_html=error.is_html)

        return OperationResult()

class InstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, installExtension)

class UninstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, uninstallExtension)

class ReinstallExtension(ExtensionOperation):
    def __init__(self):
        ExtensionOperation.__init__(self, reinstallExtension)

class ClearExtensionStorage(Operation):
    def __init__(self):
        Operation.__init__(self, { "extension_name": str,
                                   "author_name": Optional(str) })

    def process(self, db, user, extension_name, author_name=None):
        extension = getExtension(author_name, extension_name)
        extension_id = extension.getExtensionID(db, create=False)

        if extension_id is not None:
            cursor = db.cursor()
            cursor.execute("""DELETE FROM extensionstorage
                                    WHERE extension=%s
                                      AND uid=%s""",
                           (extension_id, user.id))
            db.commit()

        return OperationResult()

class AddExtensionHookFilter(Operation):
    def __init__(self):
        Operation.__init__(self, { "subject": typechecker.User,
                                   "extension": typechecker.Extension,
                                   "repository": typechecker.Repository,
                                   "filterhook_name": str,
                                   "path": str,
                                   "data": Optional(str),
                                   "replaced_filter_id": Optional(int) })

    def process(self, db, user, subject, extension, repository,
                filterhook_name, path, data=None, replaced_filter_id=None):
        if user != subject:
            Operation.requireRole(db, "administrator", user)

        path = reviewing.filters.sanitizePath(path)

        if "*" in path:
            try:
                reviewing.filters.validatePattern(path)
            except reviewing.filters.PatternError as error:
                raise OperationFailure(
                    code="invalidpattern",
                    title="Invalid path pattern",
                    message="There are invalid wild-cards in the path: %s" % error.message)

        installed_sha1, _ = extension.getInstalledVersion(db, subject)

        if installed_sha1 is False:
            raise OperationFailure(
                code="invalidrequest",
                title="Invalid request",
                message=("The extension \"%s\" must be installed first!"
                         % extension.getTitle(db)))

        manifest = extension.getManifest(sha1=installed_sha1)

        for role in manifest.roles:
            if isinstance(role, FilterHookRole) and role.name == filterhook_name:
                break
        else:
            raise OperationFailure(
                code="invalidrequest",
                title="Invalid request",
                message=("The extension doesn't have a filter hook role named %r!"
                         % filterhook_name))

        cursor = db.cursor()

        if replaced_filter_id is not None:
            cursor.execute("""SELECT 1
                                FROM extensionhookfilters
                               WHERE id=%s
                                 AND uid=%s""",
                           (replaced_filter_id, subject.id))

            if not cursor.fetchone():
                raise OperationFailure(
                    code="invalidoperation",
                    title="Invalid operation",
                    message="Filter to replace does not exist or belongs to another user!")

            cursor.execute("""DELETE
                                FROM extensionhookfilters
                               WHERE id=%s""",
                           (replaced_filter_id,))

        cursor.execute("""INSERT INTO extensionhookfilters
                                        (uid, extension, repository, name,
                                         path, data)
                               VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id""",
                       (subject.id, extension.getExtensionID(db), repository.id,
                        filterhook_name, path, data))

        filter_id, = cursor.fetchone()

        db.commit()

        return OperationResult(filter_id=filter_id)

class DeleteExtensionHookFilter(Operation):
    def __init__(self):
        Operation.__init__(self, { "subject": typechecker.User,
                                   "filter_id": int })

    def process(self, db, user, subject, filter_id):
        if user != subject:
            Operation.requireRole(db, "administrator", user)

        cursor = db.cursor()
        cursor.execute("""SELECT 1
                            FROM extensionhookfilters
                           WHERE id=%s
                             AND uid=%s""",
                       (filter_id, subject.id))

        if not cursor.fetchone():
            raise OperationFailure(
                code="invalidoperation",
                title="Invalid operation",
                message="Filter to delete does not exist or belongs to another user!")

        cursor.execute("""DELETE
                            FROM extensionhookfilters
                           WHERE id=%s""",
                       (filter_id,))

        db.commit()

        return OperationResult()
