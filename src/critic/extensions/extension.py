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

from __future__ import annotations

import asyncio
import os
import logging
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic.gitaccess import SHA1
from critic import textutils

from .manifest import MANIFEST_FILENAMES, Manifest, ManifestError
from . import getExtensionSnapshotPath


class ExtensionError(Exception):
    def __init__(self, message: str, extension: Optional[Extension] = None):
        super(ExtensionError, self).__init__(message)
        self.extension = extension


class Extension(object):
    def __init__(
        self,
        extension_id: Optional[int],
        path: str,
        publisher_name: Optional[str],
        extension_name: str,
        repository: Optional[gitaccess.GitRepository] = None,
    ):
        if os.path.sep in extension_name:
            raise ExtensionError("Invalid extension name: %s" % extension_name)

        self.id = extension_id
        self.__path = path
        self.__publisher_name = publisher_name
        self.__extension_name = extension_name
        self.__repository = repository

    def isSystemExtension(self) -> bool:
        return self.__publisher_name is None

    def getAuthorName(self) -> Optional[str]:
        if self.isSystemExtension():
            return None
        return self.__publisher_name

    def getName(self) -> str:
        return self.__extension_name

    def getKey(self):
        if self.isSystemExtension():
            return self.__extension_name
        else:
            return "%s/%s" % (self.__publisher_name, self.__extension_name)

    def getPath(self) -> str:
        return self.__path

    def getRepository(self) -> gitaccess.GitRepository:
        if self.__repository:
            return self.__repository
        return gitaccess.GitRepository.direct(self.__path)

    async def getVersions(self) -> Sequence[str]:
        prefix = "refs/heads/version/"
        try:
            versions = await self.getRepository().foreachref(pattern=prefix)
            return [version[len(prefix) :] for version in versions]
        except gitaccess.GitError:
            # Not a git repository => no versions (except "Live").
            return []

    async def getManifest(
        self, version_name: Optional[str] = None, *, sha1: Optional[SHA1] = None
    ) -> Manifest:
        path = self.__path
        filename = source = None

        if sha1 is None:
            ref = "HEAD" if version_name is None else f"version/{version_name}"
        else:
            ref = sha1
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
            manifest_sha1, wanted_object_type="blob", object_factory=gitaccess.GitBlob
        )
        source = textutils.decode(source_blob.data)

        manifest = Manifest(path=path, filename=filename, source=source)
        manifest.read()
        return manifest

    async def getCurrentSHA1(self, version_name: Optional[str]) -> SHA1:
        repository = gitaccess.GitRepository.direct(self.__path)
        ref = f"refs/heads/version/{version_name}" if version_name else "HEAD"
        return await repository.revparse(ref, object_type="commit")

    async def prepareVersionSnapshot(self, sha1: SHA1) -> None:
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

    async def prepareVersion(
        self,
        critic: api.critic.Critic,
        cursor: dbaccess.TransactionCursor,
        *,
        version_name: Optional[str] = None,
    ) -> Tuple[int, SHA1]:
        logger.info("preparing version: %s %s", self.getKey(), version_name or "<live>")

        sha1 = await self.getCurrentSHA1(version_name)
        name_check = "name IS NULL" if version_name is None else "name={name}"

        # First check if this version has already been prepared:
        async with dbaccess.Query[int](
            cursor,
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

        message = None
        manifest: Optional[Manifest]

        try:
            manifest = await self.getManifest(version_name)
        except (OSError, ManifestError) as error:
            logger.exception("invalid version")
            manifest = None
            message = str(error)

        # Mark all older versions as not the current one. (There ought to be
        # at most one that is the current one, of course.) But only do this if
        # the new version has a valid MANIFEST file, giving it at least some
        # chance to be a working version.
        if manifest:
            await cursor.execute(
                """UPDATE extensionversions
                      SET current=FALSE
                    WHERE extension={extension}
                      AND name={name}""",
                extension=self.id,
                name=version_name,
            )

        version_id = await cursor.insert(
            "extensionversions",
            dbaccess.parameters(
                extension=self.id,
                name=version_name,
                sha1=sha1,
                current=manifest is not None,
                invalid=manifest is None,
                message=message,
            ),
            returning="id",
            value_type=int,
        )

        assert version_id is not None

        logger.debug("version id: %d", version_id)

        if not manifest:
            return version_id, sha1

        for role in manifest.roles:
            await role.install(cursor, version_id)

        return version_id, sha1

    async def getAuthor(self, critic: api.critic.Critic) -> api.user.User:
        if self.isSystemExtension():
            return api.user.system(critic)
        author_name = self.getAuthorName()
        assert author_name is not None
        return await api.user.fetch(critic, name=author_name)
