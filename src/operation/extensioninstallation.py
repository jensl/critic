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

from operation import Operation, OperationResult, OperationFailure, \
                      OperationError, Optional
from extensions.installation import installExtension, uninstallExtension, \
                                    reinstallExtension, InstallationError, \
                                    getExtension

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
