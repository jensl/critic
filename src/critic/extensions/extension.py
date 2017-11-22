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

import asyncio
import os
import pwd
import logging

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic import textutils

from .manifest import MANIFEST_FILENAMES, Manifest, ManifestError
from . import getExtensionSnapshotPath


class ExtensionError(Exception):
    def __init__(self, message, extension=None):
        super(ExtensionError, self).__init__(message)
        self.extension = extension


class Extension(object):
    def __init__(self, extension_id, path, publisher_name, extension_name):
        if os.path.sep in extension_name:
            raise ExtensionError("Invalid extension name: %s" % extension_name)

        self.id = extension_id
        self.__path = path
        self.__publisher_name = publisher_name
        self.__extension_name = extension_name
        self.__manifest = {}

    def isSystemExtension(self):
        return self.__publisher_name is None

    def getAuthorName(self):
        if self.isSystemExtension():
            return None
        return self.__publisher_name

    def getName(self):
        return self.__extension_name

    def getTitle(self, db):
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

            title += author.fullname

        return title

    def getKey(self):
        if self.isSystemExtension():
            return self.__extension_name
        else:
            return "%s/%s" % (self.__publisher_name, self.__extension_name)

    def getPath(self):
        return self.__path

    def getRepository(self):
        return gitaccess.GitRepository.direct(self.__path)

    async def getVersions(self):
        prefix = "refs/heads/version/"
        try:
            versions = await self.getRepository().foreachref(pattern=prefix)
            return [version[len(prefix) :] for version in versions]
        except gitaccess.GitError:
            # Not a git repository => no versions (except "Live").
            return []

    async def getManifest(self, version_name):
        path = self.__path
        filename = source = None

        ref = "HEAD" if version_name is None else f"version/{version_name}"
        repository = self.getRepository()
        for filename in MANIFEST_FILENAMES:
            try:
                logger.debug("trying %s", f"{ref}:{filename}")
                manifest_sha1 = await repository.revparse(f"{ref}:{filename}")
            except gitaccess.GitReferenceError:
                logger.debug("- reference error")
                pass
            else:
                logger.debug("- found!")
                break
        else:
            raise ManifestError("no MANIFEST file found")
        source_blob = await repository.fetchone(
            manifest_sha1, wanted_object_type="blob"
        )
        source = textutils.decode(source_blob.data)

        manifest = Manifest(path=path, filename=filename, source=source)
        manifest.read()
        return manifest

    async def getCurrentSHA1(self, version_name):
        repository = gitaccess.GitRepository.direct(self.__path)
        ref = f"refs/heads/version/{version_name}" if version_name else "HEAD"
        return await repository.revparse(ref, object_type="commit")

    async def prepareVersionSnapshot(self, sha1):
        install_dir = getExtensionSnapshotPath()
        if os.path.isdir(os.path.join(install_dir, sha1)):
            return
        if not os.path.isdir(install_dir):
            os.makedirs(install_dir)
        pipe_read, pipe_write = os.pipe()
        git_archive = await asyncio.create_subprocess_exec(
            gitaccess.git(),
            "archive",
            "--format=tar",
            f"--prefix={sha1}/",
            sha1,
            stdout=pipe_write,
            cwd=self.__path,
        )
        os.close(pipe_write)
        tar_extract = await asyncio.create_subprocess_exec(
            "tar", "x", stdin=pipe_read, cwd=install_dir
        )
        os.close(pipe_read)
        await asyncio.gather(git_archive.wait(), tar_extract.wait())
        if git_archive.returncode != 0:
            raise ExtensionError("git-archive failed")
        if tar_extract.returncode != 0:
            raise ExtensionError("tar -x failed")

    async def prepareVersion(self, critic, cursor, *, version_name=None):
        logger.info("preparing version: %s %s", self.getKey(), version_name or "<live>")

        sha1 = await self.getCurrentSHA1(version_name)
        name_check = "name IS NULL" if version_name is None else "name={name}"

        # First check if this version has already been prepared:
        async with cursor.query(
            f"""SELECT id
                  FROM extensionversions
                 WHERE extension={{extension}}
                   AND {name_check}
                   AND sha1={{sha1}}""",
            extension=self.id,
            name=version_name,
            sha1=sha1,
        ) as result:
            version_id = await result.maybe_scalar()
            if version_id is not None:
                return version_id, sha1

        snapshot_future = None
        invalid = False
        message = None

        try:
            manifest = await self.getManifest(version_name)
        except (OSError, ManifestError) as error:
            logger.exception("invalid version")
            invalid = True
            message = str(error)

        # Mark all older versions as not the current one. (There ought to be
        # at most one that is the current one, of course.) But only do this if
        # the new version has a valid MANIFEST file, giving it at least some
        # chance to be a working version.
        if not invalid:
            await cursor.execute(
                """UPDATE extensionversions
                      SET current=FALSE
                    WHERE extension={extension}
                      AND name={name}""",
                extension=self.id,
                name=version_name,
            )

        async with cursor.query(
            """INSERT INTO extensionversions (
                        extension, name, sha1, current, invalid,
                        message
                      )
               VALUES ({extension}, {name}, {sha1}, {current},
                       {invalid}, {message})""",
            extension=self.id,
            name=version_name,
            sha1=sha1,
            current=not invalid,
            invalid=invalid,
            message=message,
            returning="id",
        ) as result:
            version_id = await result.scalar()

        logger.debug("version id: %d", version_id)

        if invalid:
            return version_id, sha1

        for role in manifest.roles:
            await role.install(cursor, version_id)

        if snapshot_future:
            await snapshot_future

        return version_id, sha1

    async def getAuthor(self, critic):
        if self.isSystemExtension():
            return api.user.system(critic)
        return await api.user.fetch(critic, name=self.getAuthorName())

    async def getExtensionID(self, critic, create=False):
        assert isinstance(create, (bool, dbaccess.Cursor))

        try:
            if self.isSystemExtension():
                author = None
                async with critic.query(
                    """SELECT id
                         FROM extensions
                        WHERE author IS NULL
                          AND name={name}""",
                    name=self.__extension_name,
                ) as result:
                    return await result.scalar()
            else:
                author = await self.getAuthor(critic)
                async with critic.query(
                    """SELECT id
                         FROM extensions
                        WHERE author={author}
                          AND name={name}""",
                    author=author,
                    name=self.__extension_name,
                ) as result:
                    return await result.scalar()
        except dbaccess.ZeroRowsInResult:
            pass

        if not create:
            return None

        async def createID(cursor):
            async with cursor.query(
                """INSERT INTO extensions (author, name)
                   VALUES ({author}, {name})""",
                author=author,
                name=self.__extension_name,
                returning="id",
            ) as result:
                return await result.scalar()

        if create is True:
            async with critic.transaction() as cursor:
                return await createID(cursor)
        else:
            return await createID(create)

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
            cursor.execute(
                """SELECT extensionversions.sha1, extensionversions.name
                     FROM extensioninstalls
          LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                    WHERE extensioninstalls.uid IS NULL
                      AND extensioninstalls.extension=%s""",
                (extension_id,),
            )
        else:
            cursor.execute(
                """SELECT extensionversions.sha1, extensionversions.name
                     FROM extensioninstalls
          LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                    WHERE extensioninstalls.uid=%s
                      AND extensioninstalls.extension=%s""",
                (user.id, extension_id),
            )

        row = cursor.fetchone()

        if row:
            return row
        else:
            return (False, False)

    @staticmethod
    async def fromId(db, extension_id):
        cursor = db.cursor()
        cursor.execute(
            """SELECT users.name, extensions.name
                 FROM extensions
      LEFT OUTER JOIN users ON (users.id=extensions.author)
                WHERE extensions.id=%s""",
            (extension_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ExtensionError("Invalid extension id: %d" % extension_id)
        publisher_name, extension_name = row
        return Extension(publisher_name, extension_name)

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
        cursor.execute(
            """SELECT extensioninstalls.id, extensioninstalls.extension,
                      extensionversions.id, extensionversions.sha1,
                      extensioninstalls.uid IS NULL
                 FROM extensioninstalls
      LEFT OUTER JOIN extensionversions ON (extensionversions.id=extensioninstalls.version)
                WHERE uid=%s OR uid IS NULL
             ORDER BY uid ASC NULLS FIRST""",
            (user.id if user else None,),
        )

        install_per_extension = {}

        # Since we ordered by 'uid' with nulls ("universal installs") first,
        # we'll overwrite universal installs with per-user installs, as intended.
        for install_id, extension_id, version_id, version_sha1, is_universal in cursor:
            install_per_extension[extension_id] = (
                install_id,
                version_id,
                version_sha1,
                is_universal,
            )

        installs = [
            (install_id, extension_id, version_id, version_sha1, is_universal)
            for extension_id, (
                install_id,
                version_id,
                version_sha1,
                is_universal,
            ) in install_per_extension.items()
        ]

        # Sort installs by install id, higher first.  This means a later install
        # takes precedence over an earlier, if they both handle the same path.
        installs.sort(reverse=True)

        # Drop the install_id; it is not relevant past this point.
        return [
            (extension_id, version_id, version_sha1, is_universal)
            for _, extension_id, version_id, version_sha1, is_universal in installs
        ]

    @staticmethod
    def getUpdatedExtensions(db, user):
        cursor = db.cursor()
        cursor.execute(
            """SELECT users.name, users.fullname, extensions.name,
                      extensionversions.name, extensionversions.sha1
                 FROM users
                 JOIN extensions ON (extensions.author=users.id)
                 JOIN extensionversions ON (extensionversions.extension=extensions.id)
                 JOIN extensioninstalls ON (extensioninstalls.version=extensionversions.id)
                WHERE extensioninstalls.uid=%s""",
            (user.id,),
        )

        updated = []
        for (
            publisher_name,
            author_fullname,
            extension_name,
            version_name,
            version_sha1,
        ) in cursor:
            extension = Extension(publisher_name, extension_name)
            if extension.getCurrentSHA1(version_name) != version_sha1:
                updated.append((author_fullname, extension_name))
        return updated


def find(critic):
    def search(user_name, search_dir):
        if not search_dir:
            return []

        if not (os.path.isdir(search_dir) and os.access(search_dir, os.X_OK | os.R_OK)):
            return []

        extensions = []

        for extension_name in os.listdir(search_dir):
            extension_dir = os.path.join(search_dir, extension_name)

            if not (
                os.path.isdir(extension_dir)
                and os.access(extension_dir, os.X_OK | os.R_OK)
            ):
                continue

            for filename in MANIFEST_FILENAMES:
                manifest_path = os.path.join(extension_dir, filename)
                if os.access(manifest_path, os.R_OK):
                    extensions.append(Extension(user_name, extension_name))
                    break

        return extensions

    settings = api.critic.settings().extensions

    if not settings.enabled:
        return []

    extensions = search(None, settings.system_dir)

    if settings.user_dir and not critic.effective_user.is_anonymous:
        try:
            pwd_entry = pwd.getpwnam(critic.effective_user.name)
        except KeyError:
            pass
        else:
            user_dir = os.path.join(pwd_entry.pw_dir, settings.user_dir)
            extensions.extend(search(critic.effective_user.name, user_dir))

    return extensions
