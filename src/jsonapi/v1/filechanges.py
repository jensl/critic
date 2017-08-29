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

import re

import api
import jsonapi

@jsonapi.PrimaryResource
class FileChanges(object):
    """File changes for a changeset"""

    name = "filechanges"
    contexts = (None, "repositories", "changesets")
    value_class = api.filechange.FileChange
    exceptions = (api.filechange.FileChangeError,)

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer, // the file's id
             "path": string, // the file's path
             "changeset": integer, // the changeset's id
             "old_sha1": string, // the sha1 identifying the file's old blob
             "old_mode": string, // the old file permissions
             "new_sha1": string, // the sha1 identifying the file's new blob
             "new_mode": string, // the new file permissions
           }"""

        return parameters.filtered(
            "filechanges", {
                "file": value.file,
                "changeset": value.changeset,
                "old_sha1": value.old_sha1,
                "old_mode": value.old_mode,
                "new_sha1": value.new_sha1,
                "new_mode": value.new_mode
            })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) filechanges (changed files).

           FILE_ID : integer

           Retrieve the changes to a file identified by its unique numeric id.

           changeset : CHANGESET : -

           Retrieve the changes from a changeset identified by its unique numeric id.

           reposititory : REPOSITORY : -

           The repository in which the files exist."""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        file = api.file.fetch(parameters.critic, jsonapi.numeric_id(argument))

        return FileChanges.setAsContext(
            parameters, api.filechange.fetch(
                parameters.critic, changeset, file))

    @staticmethod
    def multiple(parameters):
        """Retrieve all filechanges (changed files) from a changeset.

           changeset : CHANGESET : -

           Retrieve the changed from a changeset indentified by its unique numeric id.

           reposititory : REPOSITORY : -

           The repository in which the files exist."""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        return api.filechange.fetchAll(parameters.critic, changeset)

    @staticmethod
    def deduce(parameters):
        changeset = jsonapi.deduce("v1/changesets", parameters)
        if changeset is None:
            raise jsonapi.UsageError(
                "changeset needs to be specified, ex. &changeset=<id>")
        filechange = parameters.context.get(FileChanges.name)
        filechange_parameter = parameters.getQueryParameter("filechange")
        if filechange_parameter is not None:
            if filechange is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: filechange=%s"
                    % filechange_parameter)
            filechange_id = jsonapi.numeric_id(filechange_parameter)
            filechange = api.filechange.fetch(
                parameters.critic, changeset, filechange_id)
        return filechange

    @staticmethod
    def setAsContext(parameters, filechange):
        parameters.setContext(FileChanges.name, filechange)
        return filechange

    @staticmethod
    def resource_id(value):
        return value.file.id
