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

from critic import auth

from .extension import Extension, ExtensionError


class InstallationError(Exception):
    def __init__(self, title, message):
        self.title = title
        self.message = message


async def doInstallExtension(critic, extension, version):
    await auth.AccessControl.accessExtension(extension, "install")

    user = critic.effective_user
    is_universal = user.is_anonymous
    extension_id = await extension.getExtensionID(critic, create=True)
    manifest = await extension.getManifest(version=version)

    # Detect conflicting extension installs.
    installed_extensions = await api.extension.fetchAll(critic, installed_by=user)
    for installed_extension in installed_extensions:
        installation = await installed_extension.installation

        # Two installs never conflict if one is universal and one is not.
        if is_universal != installation.is_universal:
            continue

        # Same extension => conflict
        #
        # The web UI will typically not let you try to do this; if the extension
        # is already installed the UI will only let you uninstall or upgrade it.
        # But you never know.  Also, there's a UNIQUE constraint in the database
        # that would prevent this, but with a significantly worse error message,
        # of course.
        if installed_extension == extension:
            key = await installed_extension.key
            raise InstallationError(
                title="Conflicting install",
                message=(
                    "The extension %s is already %sinstalled."
                    % (key, "universally " if is_universal else "")
                ),
            )

        # Different extensions, same name => also conflict
        #
        # Two extensions with the same name are probably simply two forks of the
        # same extension, and are very likely to have overlapping and
        # conflicting functionality.  Also, extension resource paths only
        # contain the extension name as an identifier, and thus will conflict
        # between the two extensions, even if they are actually completely
        # unrelated.
        if installed_extension.name == extension.name:
            installed_key = await installed_extension.key
            key = await extension.key
            raise InstallationError(
                title="Conflicting install",
                message=(
                    "The extension %s is already %sinstalled, and "
                    "conflicts with the extension %s since they have the "
                    "same name."
                    % (
                        installed_key,
                        "universally " if installation.is_universal else "",
                        key,
                    )
                ),
            )

    cursor = db.cursor()

    if is_universal:
        user_id = None
    else:
        user_id = user.id

    if version is not None:
        sha1 = extension.prepareVersionSnapshot(version)

        cursor.execute(
            """SELECT id
                 FROM extensionversions
                WHERE extension=%s
                  AND name=%s
                  AND sha1=%s""",
            (extension_id, version, sha1),
        )
        row = cursor.fetchone()

        if row:
            (version_id,) = row
        else:
            cursor.execute(
                """INSERT INTO extensionversions (extension, name, sha1)
                   VALUES (%s, %s, %s)
                RETURNING id""",
                (extension_id, version, sha1),
            )
            (version_id,) = cursor.fetchone()

            for role in manifest.roles:
                role.install(db, version_id)
    else:
        version_id = None

    cursor.execute(
        """INSERT INTO extensioninstalls (uid, extension, version)
           VALUES (%s, %s, %s)""",
        (user_id, extension_id, version_id),
    )


def doUninstallExtension(db, user, extension):
    extension_id = extension.getExtensionID(db)

    if extension_id is None:
        return

    cursor = db.cursor()

    if user is not None:
        cursor.execute(
            """DELETE FROM extensioninstalls
                WHERE uid=%s
                  AND extension=%s""",
            (user.id, extension_id),
        )
    else:
        cursor.execute(
            """DELETE FROM extensioninstalls
                WHERE uid IS NULL
                  AND extension=%s""",
            (extension_id,),
        )


def getExtension(author_name, extension_name):
    """Create an Extension object ignoring whether it is valid"""
    try:
        return Extension(author_name, extension_name)
    except ExtensionError as error:
        if error.extension is None:
            raise error
        return error.extension


def installExtension(db, user, author_name, extension_name, version):
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()


def uninstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, getExtension(author_name, extension_name))
    db.commit()


def reinstallExtension(db, user, author_name, extension_name, version):
    doUninstallExtension(db, user, getExtension(author_name, extension_name))
    doInstallExtension(db, user, Extension(author_name, extension_name), version)
    db.commit()
