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

from extensions.extension import Extension

def doInstallExtension(db, user, extension, version):
    extension_id = extension.getExtensionID(db, create=True)
    manifest = extension.readManifest(version)

    cursor = db.cursor()

    if version is None:
        sha1 = None
        cursor.execute("SELECT id FROM extensionversions WHERE extension=%s AND sha1 IS NULL", (extension_id,))
    else:
        sha1 = extension.prepareVersionSnapshot(version)
        cursor.execute("SELECT id FROM extensionversions WHERE extension=%s AND sha1=%s", (extension_id, sha1))

    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO extensionversions (extension, name, sha1) VALUES (%s, %s, %s) RETURNING id", (extension_id, version, sha1))
        row = cursor.fetchone()

    version_id = row[0]

    for role in manifest.roles:
        role.install(cursor, version_id, user)

def doUninstallExtension(db, user, extension):
    extension_id = extension.getExtensionID(db)

    if extension_id is None:
        return

    cursor = db.cursor()

    cursor.execute("""DELETE FROM extensionroles
                            USING extensions, extensionversions
                            WHERE extensions.id=%s
                              AND extensionversions.extension=extensions.id
                              AND extensionroles.version=extensionversions.id
                              AND extensionroles.uid=%s""",
                   (extension_id, user.id))

def installExtension(db, user, author_name, extension_name, version):
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()

def uninstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, Extension(author_name, extension_name))
    db.commit()

def reinstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, Extension(author_name, extension_name))
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()
