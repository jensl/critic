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
class Filechanges(object):
    """Filechanges for a changeset"""

    name = "filechanges"
    contexts = (None, "changesets")
    value_class = api.filechange.Filechange
    exceptions = (api.filechange.FilechangeError,)

    @staticmethod
    def json(value, parameters):
        """Filechanges {
             "id": integer, // the file's id
             "changeset": integer, // the changeset's id
             "path": string, // the file's path
             "old_sha1": string, // the sha1 identifying the file's old blob
             "old_mode": string, // the old file permissions
             "new_sha1": string, // the sha1 identifying the file's new blob
             "new_mode": string, // the new file permissions
             "chunks": Chunk[],
           }

           Chunk {
             "deleteoffset": integer, // offset for deleted rows
             "deletecount": integer, // number of deleted rows
             "insertoffset": integer, // offset for inserted rows
             "insertcount": integer, // number of inserted rows
             "analysis": string,
             "is_whitespace": integer, // whether or not the chunk is entirely whitespace
           }"""

        def chunks_as_json(chunks):
            return [{ "deleteoffset": chunk.deleteoffset,
                      "deletecount": chunk.deletecount,
                      "insertoffset": chunk.insertoffset,
                      "insertcount": chunk.insertcount,
                      "analysis": chunk.analysis,
                      "is_whitespace": chunk.is_whitespace
                  } for chunk in chunks]

        return parameters.filtered(
            "filechanges", { "id": value.id,
                             "changeset": value.changeset,
                             "path": value.path,
                             "old_sha1": value.old_sha1,
                             "old_mode": value.old_mode,
                             "new_sha1": value.new_sha1,
                             "new_mode": value.new_mode,
                             "chunks": chunks_as_json(value.chunks)})

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
        return api.filechange.fetch(
            parameters.critic, changeset, jsonapi.numeric_id(argument))

    @staticmethod
    def multiple(parameters):
        """Retrieve all filechanges (changed files) from a changeset.

           changeset : CHANGESET : -

           Retrieve the changed from a changeset indentified by its unique numeric id.

           reposititory : REPOSITORY : -

           The repository in which the files exist."""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        return api.filechange.fetchAll(parameters.critic, changeset)
