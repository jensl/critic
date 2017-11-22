# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

from typing import Iterable, Sequence, Optional

from critic import api
from critic.gitaccess import SHA1


class Error(api.APIError, object_type="file change"):
    pass


class InvalidId(api.InvalidIdError, Error):
    pass


class InvalidIds(api.InvalidIdsError, Error):
    pass


class FileChange(api.APIObject):
    """Representation of the changes to a file introduced by a changeset"""

    def __hash__(self) -> int:
        return hash((self.changeset, self.file))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileChange)
            and self.changeset == other.changeset
            and self.file == other.file
        )

    def __lt__(self, other: object) -> bool:
        return isinstance(other, FileChange) and (
            self.changeset < other.changeset
            or (self.changeset == other.changeset and self.file < other.file)
        )

    @property
    def changeset(self) -> api.changeset.Changeset:
        return self._impl.changeset

    @property
    def file(self) -> api.file.File:
        return self._impl.file

    @property
    def old_sha1(self) -> Optional[SHA1]:
        return self._impl.old_sha1

    @property
    def old_mode(self) -> Optional[int]:
        return self._impl.old_mode

    @property
    def new_sha1(self) -> Optional[SHA1]:
        return self._impl.new_sha1

    @property
    def new_mode(self) -> Optional[int]:
        return self._impl.new_mode

    @property
    def was_added(self) -> bool:
        return self._impl.old_sha1 is None

    @property
    def was_deleted(self) -> bool:
        return self._impl.new_sha1 is None


async def fetch(changeset: api.changeset.Changeset, file: api.file.File) -> FileChange:
    from .impl import filechange as impl

    return await impl.fetch(changeset.critic, changeset, file)


async def fetchMany(
    changeset: api.changeset.Changeset, files: Iterable[api.file.File]
) -> Sequence[FileChange]:
    from .impl import filechange as impl

    return await impl.fetchMany(changeset.critic, changeset, list(files))


async def fetchAll(changeset: api.changeset.Changeset) -> Sequence[FileChange]:
    from .impl import filechange as impl

    return await impl.fetchAll(changeset)


resource_name = "filechanges"
table_name = "changesetfiles"
