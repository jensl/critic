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

import logging
import re
from typing import Sequence, Optional, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic import jsonapi


class Trees(jsonapi.ResourceClass[api.tree.Tree], api_module=api.tree):
    """Tree objects in Git repositories"""

    contexts = (None, "repositories", "commits")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.tree.Tree
    ) -> jsonapi.JSONResult:
        json_entries = [
            {
                "mode": entry.mode,
                "name": entry.name,
                "sha1": entry.sha1,
                "size": entry.size,
            }
            for entry in value.entries
        ]
        for json_entry, entry in zip(json_entries, value.entries):
            if entry.isSymbolicLink:
                json_entry["target"] = await value.readLink(entry)
        return {
            "repository": value.repository,
            "sha1": value.sha1,
            "entries": json_entries,
        }

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.tree.Tree, Sequence[api.tree.Tree]]:
        sha1_parameter = parameters.getQueryParameter(
            "sha1", converter=gitaccess.as_sha1
        )
        path_parameter = parameters.getQueryParameter("path")

        if sha1_parameter is not None and path_parameter is not None:
            raise jsonapi.UsageError("Conflicting parameters: 'sha1' and 'path'")

        if sha1_parameter is not None:
            repository = await Repositories.deduce(parameters)
            if not repository:
                raise jsonapi.UsageError("Missing parameter: 'repository'")
            if re.match("[0-9A-Fa-f]{40}$", sha1_parameter):
                sha1 = sha1_parameter
            else:
                sha1 = await repository.resolveRef(sha1_parameter, expect="tree")
            return await api.tree.fetch(repository=repository, sha1=sha1)

        if path_parameter is not None:
            commit = await Commits.deduce(parameters)
            if not commit:
                raise jsonapi.UsageError("Missing parameter: 'commit'")
            return await api.tree.fetch(commit=commit, path=path_parameter)

        raise jsonapi.UsageError(
            "Missing parameter: one of 'sha1' or 'path' must be specified"
        )


from .commits import Commits
from .repositories import Repositories
