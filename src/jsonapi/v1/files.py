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

import api
import jsonapi

@jsonapi.PrimaryResource
class Files(object):
    """Files (path <=> id mappings) in the system."""

    name = "files"
    value_class = api.file.File
    exceptions = api.file.FileError

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer,
             "path": string
           }"""

        return parameters.filtered(
            "files", { "id": value.id,
                       "path": value.path })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) files.

           FILE_ID : integer

           Retrieve a file identified by its unique numeric id."""

        return api.file.fetch(
            parameters.critic, file_id=jsonapi.numeric_id(argument))

    @staticmethod
    def multiple(parameters):
        """Retrieve a file by its path.

           path : PATH : string

           Retrieve the file with the specified path. (Required)"""

        path = parameters.getQueryParameter("path")
        if path is None:
            raise UsageError("No path parameter specified")

        return api.file.fetch(parameters.critic, path=path)

    @staticmethod
    def fromParameter(value, parameters):
        file_id, path = jsonapi.id_or_name(value)
        return api.file.fetch(parameters.critic, file_id, path=path)
