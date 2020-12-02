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

from typing import Any, Dict, Sequence, Optional

from critic import api
from ..parameters import Parameters
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import numeric_id


async def _requireChangeset(parameters: Parameters) -> api.changeset.Changeset:
    changeset = await parameters.deduce(api.changeset.Changeset)
    if not changeset:
        raise UsageError.missingParameter("changeset")
    return changeset


class FileChanges(ResourceClass[api.filechange.FileChange], api_module=api.filechange):
    """File changes for a changeset"""

    contexts = (None, "repositories", "changesets")

    @staticmethod
    async def json(
        parameters: Parameters, value: api.filechange.FileChange
    ) -> JSONResult:
        """{
          "id": integer, // the file's id
          "path": string, // the file's path
          "changeset": integer, // the changeset's id
          "old_sha1": string, // the sha1 identifying the file's old blob
          "old_mode": string, // the old file permissions
          "new_sha1": string, // the sha1 identifying the file's new blob
          "new_mode": string, // the new file permissions
        }"""

        return {
            "file": value.file,
            "changeset": value.changeset,
            "old_sha1": value.old_sha1,
            "old_mode": value.old_mode,
            "new_sha1": value.new_sha1,
            "new_mode": value.new_mode,
        }

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> api.filechange.FileChange:
        """Retrieve one (or more) filechanges (changed files).

        FILE_ID : integer

        Retrieve the changes to a file identified by its unique numeric id.

        changeset : CHANGESET : -

        Retrieve the changes from a changeset identified by its unique
        numeric id.

        reposititory : REPOSITORY : -

        The repository in which the files exist."""

        return await api.filechange.fetch(
            await _requireChangeset(parameters),
            await api.file.fetch(parameters.critic, numeric_id(argument)),
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
    ) -> Sequence[api.filechange.FileChange]:
        """Retrieve all filechanges (changed files) from a changeset.

        changeset : CHANGESET : -

        Retrieve the changed from a changeset indentified by its unique
        numeric id.

        reposititory : REPOSITORY : -

        The repository in which the files exist."""

        return await api.filechange.fetchAll(await _requireChangeset(parameters))

    @classmethod
    async def deduce(
        cls,
        parameters: Parameters,
    ) -> Optional[api.filechange.FileChange]:
        changeset = await parameters.deduce(api.changeset.Changeset)
        if changeset is None:
            raise UsageError("changeset needs to be specified, ex. &changeset=<id>")
        filechange = parameters.in_context(api.filechange.FileChange)
        filechange_parameter = parameters.query.get("filechange")
        if filechange_parameter is not None:
            if filechange is not None:
                raise UsageError.redundantParameter("filechange")
            file_id = numeric_id(filechange_parameter)
            filechange = await api.filechange.fetch(
                changeset, await api.file.fetch(parameters.critic, file_id)
            )
        return filechange

    @staticmethod
    def resource_id(value: api.filechange.FileChange) -> int:
        return value.file.id

    @staticmethod
    def sort_key(item: Dict[str, Any]) -> Any:
        return (item["changeset"], item["file"])
