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

import base
import configuration
import dbutils

from extensions.manifest import Manifest, PageRole, InjectRole, ProcessChangesRole, ProcessCommitsRole

class Extension:
    def __init__(self, author_name, extension_name):
        self.__author_name = author_name
        self.__extension_name = extension_name
        self.__path = os.path.join(configuration.extensions.SEARCH_ROOT, author_name, "CriticExtensions", extension_name)

    def getAuthorName(self):
        return self.__author_name

    def getName(self):
        return self.__extension_name

    def getKey(self):
        return "%s/%s" % (self.__author_name, self.__extension_name)

    def getPath(self):
        return self.__path

    def getVersions(self):
        try:
            branches = subprocess.check_output([configuration.executables.GIT, "branch"], cwd=self.__path).splitlines()
            return [branch[10:].strip() for branch in branches if branch[2:].startswith("version/")]
        except subprocess.CalledProcessError:
            # Not a git repository => no versions (except "Live").
            return []

    def readManifest(self, version=None):
        if version is None:
            source = None
        else:
            source = subprocess.check_output([configuration.executables.GIT, "cat-file", "blob", "version/%s:MANIFEST" % version],
                                             cwd=self.__path)

        manifest = Manifest(self.__path, source)
        manifest.read()
        return manifest

    def getCurrentSHA1(self, version):
        return subprocess.check_output([configuration.executables.GIT, "rev-parse", "--verify", "version/%s" % version],
                                       cwd=self.__path).strip()

    def prepareVersionSnapshot(self, version):
        sha1 = self.getCurrentSHA1(version)

        if not os.path.isdir(os.path.join(configuration.extensions.INSTALL_DIR, sha1)):
            git_archive = subprocess.Popen([configuration.executables.GIT, "archive", "--format=tar", "--prefix=%s/" % sha1, sha1],
                                           stdout=subprocess.PIPE, cwd=self.__path)
            subprocess.check_call([configuration.executables.TAR, "x"], stdin=git_archive.stdout,
                                  cwd=configuration.extensions.INSTALL_DIR)

        return sha1

    def getAuthor(self, db):
        return dbutils.User.fromName(db, self.__author_name)

    def getExtensionID(self, db, create=False):
        author_id = self.getAuthor(db).id

        cursor = db.cursor()
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
        cursor.execute("""SELECT DISTINCT extensionversions.sha1, extensionversions.name
                            FROM extensionversions
                            JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                           WHERE extensionversions.extension=%s
                             AND extensionroles.uid=%s""",
                       (extension_id, user.id))
        versions = set(cursor)

        if len(versions) > 1:
            raise base.ImplementationError(
                "multiple extension versions installed (should not happen)")

        if versions:
            return versions.pop()
        else:
            return (False, False)

    def getInstallationStatus(self, db, user, version=None):
        author = self.getAuthor(db)
        manifest = self.readManifest(version)

        cursor = db.cursor()
        version_ids = set()
        installed_roles = 0

        for role in manifest.roles:
            if isinstance(role, PageRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_page ON (extensionroles_page.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_page.uid=%s
                                     AND extensionroles_page.path=%s
                                     AND extensionroles_page.script=%s
                                     AND extensionroles_page.function=%s""",
                               (author.id, self.__extension_name, user.id, role.regexp, role.script, role.function))
            elif isinstance(role, InjectRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_inject ON (extensionroles_inject.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_inject.uid=%s
                                     AND extensionroles_inject.path=%s
                                     AND extensionroles_inject.script=%s
                                     AND extensionroles_inject.function=%s""",
                               (author.id, self.__extension_name, user.id, role.regexp, role.script, role.function))
            elif isinstance(role, ProcessCommitsRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_processcommits ON (extensionroles_processcommits.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_processcommits.uid=%s
                                     AND extensionroles_processcommits.script=%s
                                     AND extensionroles_processcommits.function=%s""",
                               (author.id, self.__extension_name, user.id, role.script, role.function))
            elif isinstance(role, ProcessChangesRole):
                cursor.execute("""SELECT extensionversions.id
                                    FROM extensions
                                    JOIN extensionversions ON (extensionversions.extension=extensions.id)
                                    JOIN extensionroles_processchanges ON (extensionroles_processchanges.version=extensionversions.id)
                                   WHERE extensions.author=%s
                                     AND extensions.name=%s
                                     AND extensionroles_processchanges.uid=%s
                                     AND extensionroles_processchanges.script=%s
                                     AND extensionroles_processchanges.function=%s""",
                               (author.id, self.__extension_name, user.id, role.script, role.function))
            else:
                continue

            row = cursor.fetchone()
            if row:
                version_ids.add(row[0])
                installed_roles += 1
                role.installed = True
            else:
                role.installed = False

        if installed_roles == 0:
            manifest.status = "none"
        elif installed_roles < len(manifest.roles) or len(version_ids) != 1:
            manifest.status = "partial"
        else:
            manifest.status = "installed"

        return manifest

    @staticmethod
    def getUpdatedExtensions(db, user):
        cursor = db.cursor()
        cursor.execute("""SELECT DISTINCT users.name, users.fullname, extensions.name, extensionversions.name, extensionversions.sha1
                            FROM users
                            JOIN extensions ON (extensions.author=users.id)
                            JOIN extensionversions ON (extensionversions.extension=extensions.id)
                            JOIN extensionroles ON (extensionroles.version=extensionversions.id)
                           WHERE extensionroles.uid=%s
                             AND extensionversions.sha1 IS NOT NULL""",
                       (user.id,))

        updated = []
        for author_name, author_fullname, extension_name, version_name, sha1 in cursor:
            extension = Extension(author_name, extension_name)
            if extension.getCurrentSHA1(version_name) != sha1:
                updated.append((author_fullname, extension_name))
        return updated

    @staticmethod
    def find():
        extensions = []

        for user_directory in os.listdir(configuration.extensions.SEARCH_ROOT):
            try:
                for extension_directory in os.listdir(os.path.join(configuration.extensions.SEARCH_ROOT, user_directory, "CriticExtensions")):
                    extension_path = os.path.join(configuration.extensions.SEARCH_ROOT, user_directory, "CriticExtensions", extension_directory)

                    if os.path.isdir(extension_path) and os.access(extension_path, os.X_OK | os.R_OK):
                        manifest_path = os.path.join(extension_path, "MANIFEST")

                        if os.path.isfile(manifest_path) and os.access(manifest_path, os.R_OK):
                            extensions.append(Extension(user_directory, extension_directory))
            except OSError:
                pass

        return extensions
