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

from typing import Any, Dict, Sequence, Optional, Union

from critic import api
from critic import jsonapi


class FileChanges(
    jsonapi.ResourceClass[api.filechange.FileChange], api_module=api.filechange
):
    """File changes for a changeset"""

    contexts = (None, "repositories", "changesets")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.filechange.FileChange
    ) -> jsonapi.JSONResult:
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

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
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
            await Changesets.deduce(parameters, required=True),
            await api.file.fetch(parameters.critic, jsonapi.numeric_id(argument)),
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[api.filechange.FileChange]:
        """Retrieve all filechanges (changed files) from a changeset.

           changeset : CHANGESET : -

           Retrieve the changed from a changeset indentified by its unique
           numeric id.

           reposititory : REPOSITORY : -

           The repository in which the files exist."""

        return await api.filechange.fetchAll(
            await Changesets.deduce(parameters, required=True)
        )

    @staticmethod
    async def deduce(
        parameters: jsonapi.Parameters,
    ) -> Optional[api.filechange.FileChange]:
        changeset = await Changesets.deduce(parameters)
        if changeset is None:
            raise jsonapi.UsageError(
                "changeset needs to be specified, ex. &changeset=<id>"
            )
        filechange = parameters.context.get(FileChanges.name)
        filechange_parameter = parameters.getQueryParameter("filechange")
        if filechange_parameter is not None:
            if filechange is not None:
                raise jsonapi.UsageError.redundantParameter("filechange")
            file_id = jsonapi.numeric_id(filechange_parameter)
            filechange = await api.filechange.fetch(
                changeset, await api.file.fetch(parameters.critic, file_id)
            )
        return filechange

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, filechange: api.filechange.FileChange
    ) -> None:
        parameters.setContext(FileChanges.name, filechange)

    @staticmethod
    def resource_id(value: api.filechange.FileChange) -> int:
        return value.file.id

    @staticmethod
    def sort_key(item: Dict[str, Any]) -> Any:
        return (item["changeset"], item["file"])


from .changesets import Changesets
