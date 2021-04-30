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

from typing import Optional

from critic import api
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONResult
from ..utils import id_or_name, numeric_id


class Files(ResourceClass[api.file.File], api_module=api.file):
    """Files (path <=> id mappings) in the system."""

    @staticmethod
    async def json(parameters: Parameters, value: api.file.File) -> JSONResult:
        """{
          "id": integer,
          "path": string
        }"""

        return {"id": value.id, "path": value.path}

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.file.File:
        """Retrieve one (or more) files.

        FILE_ID : integer

        Retrieve a file identified by its unique numeric id."""

        return await api.file.fetch(parameters.critic, numeric_id(argument))

    @staticmethod
    async def multiple(parameters: Parameters) -> api.file.File:
        """Retrieve a file by its path.

        path : PATH : string

        Retrieve the file with the specified path. (Required)"""

        path = parameters.query.get("path")
        if path is None:
            raise UsageError("No path parameter specified")

        return await api.file.fetch(
            parameters.critic, path=path, create_if_missing=True
        )

    @staticmethod
    async def fromParameterValue(parameters: Parameters, value: str) -> api.file.File:
        critic = parameters.critic
        file_id, path = id_or_name(value)
        if file_id is not None:
            return await api.file.fetch(critic, file_id)
        assert path is not None
        return await api.file.fetch(critic, path=path, create_if_missing=True)

    @classmethod
    async def deduce(cls, parameters: Parameters) -> Optional[api.file.File]:
        file_obj = parameters.in_context(api.file.File)
        file_parameter = parameters.query.get("file")
        if file_parameter is not None:
            if file_obj is not None:
                raise UsageError.redundantParameter("file")
            return await Files.fromParameterValue(parameters, file_parameter)
        return file_obj
