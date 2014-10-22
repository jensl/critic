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
import subprocess
import pwd

import dbutils
import htmlutils

from extensions.manifest import Manifest, ManifestError
from extensions import getExtensionInstallPath

class ExtensionError(Exception):
    def __init__(self, message, extension=None):
        super(ExtensionError, self).__init__(message)
        self.extension = extension

class Extension(object):
    def __init__(self, author_name, extension_name):
        import configuration

        if os.path.sep in extension_name:
            raise ExtensionError(
                "Invalid extension name: %s" % extension_name)

        self.__author_name = author_name
        self.__extension_name = extension_name
        self.__manifest = {}

        if author_name:
            try:
                user_home_dir = pwd.getpwnam(author_name).pw_dir
            except KeyError:
                raise ExtensionError(
                    "No such system user: %s" % author_name,
                    extension=self)

            self.__path = os.path.join(
                user_home_dir,
                configuration.extensions.USER_EXTENSIONS_DIR,
                extension_name)
        else:
            self.__path = os.path.join(
                configuration.extensions.SYSTEM_EXTENSIONS_DIR,
                extension_name)

        if not (os.path.isdir(self.__path) and
                os.access(self.__path, os.R_OK | os.X_OK)):
            raise ExtensionError(
                "Invalid or inaccessible extension dir: %s" % self.__path,
                extension=self)

    def isSystemExtension(self):
        return self.__author_name is None

    def getAuthorName(self):
        if self.isSystemExtension():
            return None
        return self.__author_name

    def getName(self):
        return self.__extension_name

    def getTitle(self, db, html=False):
        if html:
            title = "<b>%s</b>" % htmlutils.htmlify(self.getName())
        else:
            title = self.getName()

        if not self.isSystemExtension():
            author = self.getAuthor(db)

            try:
                manifest = self.getManifest()
            except ManifestError:
                # Can't access information from the manifest, so assume "yes".
                is_author = True
            else:
                is_author = manifest.isAuthor(db, author)

            if is_author:
                title += " by "
            else:
                title += " hosted by "

            if html:
                title += htmlutils.htmlify(author.fullname)
            else:
                title += author.fullname

        return title

    def getKey(self):
        if self.isSystemExtension():
            return self.__extension_name
        else:
            return "%s/%s" % (self.__author_name, self.__extension_name)

    def getPath(self):
        return self.__path

    def getVersions(self):
        import configuration

        try:
            output = subprocess.check_output(
                [configuration.executables.GIT, "for-each-ref",
                 "--format=%(refname)", "refs/heads/version/"],
                stderr=subprocess.STDOUT, cwd=self.__path)
        except subprocess.CalledProcessError:
            # Not a git repository => no versions (except "Live").
            return []

        versions = []
        for ref in output.splitlines():
            if ref.startswith("refs/heads/version/"):
                versions.append(ref[len("refs/heads/version/"):])
        return versions

    def getManifest(self, version=None, sha1=None):
        import configuration

        path = self.__path
        source = None

        if sha1 is not None:
            if sha1 in self.__manifest:
                return self.__manifest[sha1]

            install_path = getExtensionInstallPath(sha1)
            with open(os.path.join(install_path, "MANIFEST")) as manifest_file:
                source = manifest_file.read()

            path = "<snapshot of commit %s>" % sha1[:8]
        elif version in self.__manifest:
            return self.__manifest[version]

        if source is None and version is not None:
            source = subprocess.check_output(
                [configuration.executables.GIT, "cat-file", "blob",
                 "version/%s:MANIFEST" % version],
                cwd=self.__path)

        manifest = Manifest(path, source)
        manifest.read()

        if sha1 is not None:
            self.__manifest[sha1] = manifest
        else:
            self.__manifest[version] = manifest

        return manifest

    def getCurrentSHA1(self, version):
        import configuration

        return subprocess.check_output(
            [configuration.executables.GIT, "rev-parse", "--verify",
             "version/%s" % version],
            cwd=self.__path).strip()

    def prepareVersionSnapshot(self, version):
        import configuration

        sha1 = self.getCurrentSHA1(version)

        if not os.path.isdir(getExtensionInstallPath(sha1)):
            git_archive = subprocess.Popen(
                [configuration.executables.GIT, "archive", "--format=tar",
                 "--prefix=%s/" % sha1, sha1],
                stdout=subprocess.PIPE, cwd=self.__path)
            subprocess.check_call(
                [configuration.executables.TAR, "x"],
                stdin=git_archive.stdout,
                cwd=configuration.extensions.INSTALL_DIR)

        return sha1

    def getAuthor(self, db):
        if self.isSystemExtension():
            return None
        return dbutils.User.fromName(db, self.getAuthorName())

    def getExtensionID(self, db, create=False):
        cursor = db.cursor()

        if self.isSystemExtension():
            author_id = None
            cursor.execute("""SELECT extensions.id
                                FROM extensions
                               WHERE extensions.author IS NULL
                                 AND extensions.name=%s""",
                           (self.__extension_name,))
        else:
            author_id = self.getAuthor(db).id
            cursor.execute("""SELECT extensions.id
                                FROM extensions
                               WHERE extensions.author=%s
                                 AND extensions.name=%s""",
                           (author_id, self.__extension_name))

        row = cursor.fetchone()

        if row:
            return row[0]
        elif create:
            cursor.execute("""INSERT INTO extensions (author, name)
                              VALUES (%s, %s)
                           RETURNING id""",
                           (author_id, self.__extension_name))
            return cursor.fetchone()[0]
        else:
            return None

    def getInstalledVersion(self, db, user):
        """Return (sha1, name) of the version currently installed by the user.

        If the user doesn't have the extension installed, return (False, False).
        If the user has the "live" version installed, return (None, None).
        """

        extension_id = self.getExtensionID(db)

        if extension_id is None:
            # An extension is recorded in the database and assigned an ID the
            # first time it's installed.  If it doesn't have an ID, then no user
            # can have any version of it installed.
            return (False, False)

        cursor = db.cursor()

        if user is None:
            cursor.execute("""SELECT extensionversions.sha1, extensionversions.name
                                FROM extensioninstalls
                     LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                               WHERE extensioninstalls.uid IS NULL
                                 AND extensioninstalls.extension=%s""",
                           (extension_id,))
        else:
            cursor.execute("""SELECT extensionversions.sha1, extensionversions.name
                                FROM extensioninstalls
                     LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                               WHERE extensioninstalls.uid=%s
                                 AND extensioninstalls.extension=%s""",
                           (user.id, extension_id))

        row = cursor.fetchone()

        if row:
            return row
        else:
            return (False, False)

    @staticmethod
    def fromId(db, extension_id):
        cursor = db.cursor()
        cursor.execute("""SELECT users.name, extensions.name
                            FROM extensions
                 LEFT OUTER JOIN users ON (users.id=extensions.author)
                           WHERE extensions.id=%s""",
                       (extension_id,))
        row = cursor.fetchone()
        if not row:
            raise ExtensionError("Invalid extension id: %d" % extension_id)
        author_name, extension_name = row
        return Extension(author_name, extension_name)

    @staticmethod
    def getInstalls(db, user):
        """
        Return a list of extension installs in effect for the specified user

        If 'user' is None, all universal extension installs are listed.

        Each install is returned as a tuple containing four elements, the
        extension id, the version id, the version SHA-1 and a boolean which is
        true if the install is universal.  For a LIVE version, the version id
        and the version SHA-1 are None.

        The list of installs is ordered by precedence; most significant install
        first, least significant install last.
        """

        cursor = db.cursor()
        cursor.execute("""SELECT extensioninstalls.id, extensioninstalls.extension,
                                 extensionversions.id, extensionversions.sha1,
                                 extensioninstalls.uid IS NULL
                            FROM extensioninstalls
                 LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                           WHERE uid=%s OR uid IS NULL
                        ORDER BY uid NULLS FIRST""",
                       (user.id if user else None,))

        install_per_extension = {}

        # Since we ordered by 'uid' with nulls ("universal installs") first,
        # we'll overwrite universal installs with per-user installs, as intended.
        for install_id, extension_id, version_id, version_sha1, is_universal in cursor:
            install_per_extension[extension_id] = (install_id, version_id,
                                                   version_sha1, is_universal)

        installs = [(install_id, extension_id, version_id, version_sha1, is_universal)
                    for extension_id, (install_id, version_id, version_sha1, is_universal)
                    in install_per_extension.items()]

        # Sort installs by install id, higher first.  This means a later install
        # takes precedence over an earlier, if they both handle the same path.
        installs.sort(reverse=True)

        # Drop the install_id; it is not relevant past this point.
        return [(extension_id, version_id, version_sha1, is_universal)
                for _, extension_id, version_id, version_sha1, is_universal
                in installs]

    @staticmethod
    def getUpdatedExtensions(db, user):
        cursor = db.cursor()
        cursor.execute("""SELECT users.name, users.fullname, extensions.name,
                                 extensionversions.name, extensionversions.sha1
                            FROM users
                            JOIN extensions ON (extensions.author=users.id)
                            JOIN extensionversions ON (extensionversions.extension=extensions.id)
                            JOIN extensioninstalls ON (extensioninstalls.version=extensionversions.id)
                           WHERE extensioninstalls.uid=%s""",
                       (user.id,))

        updated = []
        for author_name, author_fullname, extension_name, version_name, version_sha1 in cursor:
            extension = Extension(author_name, extension_name)
            if extension.getCurrentSHA1(version_name) != version_sha1:
                updated.append((author_fullname, extension_name))
        return updated

    @staticmethod
    def find(db):
        import configuration

        def search(user_name, search_dir):
            if not (os.path.isdir(search_dir) and
                    os.access(search_dir, os.X_OK | os.R_OK)):
                return []

            extensions = []

            for extension_name in os.listdir(search_dir):
                extension_dir = os.path.join(search_dir, extension_name)
                manifest_path = os.path.join(extension_dir, "MANIFEST")

                if not (os.path.isdir(extension_dir) and
                        os.access(extension_dir, os.X_OK | os.R_OK) and
                        os.access(manifest_path, os.R_OK)):
                    continue

                extensions.append(Extension(user_name, extension_name))

            return extensions

        extensions = search(None, configuration.extensions.SYSTEM_EXTENSIONS_DIR)

        if configuration.extensions.USER_EXTENSIONS_DIR:
            cursor = db.cursor()
            cursor.execute("SELECT name FROM users WHERE status!='retired' ORDER BY name ASC")

            for (user_name,) in cursor:
                try:
                    pwd_entry = pwd.getpwnam(user_name)
                except KeyError:
                    continue

                user_dir = os.path.join(
                    pwd_entry.pw_dir, configuration.extensions.USER_EXTENSIONS_DIR)

                extensions.extend(search(user_name, user_dir))

        return extensions
