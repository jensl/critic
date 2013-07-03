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

import os

import configuration
import dbutils

from extensions import getExtensionPath, getExtensionInstallPath

def get(req, db, user, path):
    cursor = db.cursor()

    extension_name, resource_path = path.split("/", 1)

    cursor.execute("""SELECT extensions.author, extensionversions.sha1
                        FROM extensions
                        JOIN extensionversions ON (extensionversions.extension=extensions.id)
                        JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                       WHERE extensions.name=%s
                         AND extensionroles.uid=%s
                       LIMIT 1""", (extension_name, user.id))

    row = cursor.fetchone()
    if not row: return None, None

    author_id, sha1 = row

    if sha1 is None:
        author = dbutils.User.fromId(db, author_id)
        extension_path = getExtensionPath(author.name, extension_name)
    else:
        extension_path = getExtensionInstallPath(sha1)

    resource_path = os.path.join(extension_path, "resources", resource_path)

    def guessContentType(name):
        try:
            name, ext = name.split(".", 1)
            return configuration.mimetypes.MIMETYPES[ext]
        except:
            return "application/octet-stream"

    if os.path.isfile(resource_path) and os.access(resource_path, os.R_OK):
        return guessContentType(resource_path), open(resource_path).read()
    else:
        return None, None
