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
import errno

import configuration

from extensions import getExtensionPath, getExtensionInstallPath

def get(req, db, user, path):
    extension_name, resource_path = path.split("/", 1)

    cursor = db.cursor()
    cursor.execute("""SELECT users.name, extensionversions.sha1
                        FROM extensions
                        JOIN extensioninstalls ON (extensioninstalls.extension=extensions.id)
             LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
             LEFT OUTER JOIN users ON (users.id=extensions.author)
                       WHERE extensions.name=%s
                         AND (extensioninstalls.uid=%s OR extensioninstalls.uid IS NULL)
                    ORDER BY extensioninstalls.uid ASC NULLS LAST
                       LIMIT 1""",
                   (extension_name, user.id))

    row = cursor.fetchone()

    if not row:
        return None, None

    author_name, version_sha1 = row

    if version_sha1 is None:
        extension_path = getExtensionPath(author_name, extension_name)
    else:
        extension_path = getExtensionInstallPath(version_sha1)

    resource_path = os.path.join(extension_path, "resources", resource_path)

    def guessContentType(name):
        try:
            name, ext = name.split(".", 1)
            return configuration.mimetypes.MIMETYPES[ext]
        except:
            return "application/octet-stream"

    try:
        with open(resource_path) as resource_file:
            resource = resource_file.read()
    except IOError as error:
        if error.errno in (errno.ENOENT, errno.EACCES):
            return None, None
        raise
    else:
        return guessContentType(resource_path), resource
