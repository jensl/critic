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
class Filecontents(object):
    """Context lines for a file in a commit"""

    name = "filecontents"
    contexts = (None, "repositories")
    value_class = api.filecontent.Filecontent
    exceptions = (api.filecontent.FilecontentError,)

    @staticmethod
    def json(value, parameters):
        """TODO: add documentation"""

        def part_as_dict(part):
            dict_part = {
                "type": part.type,
                "content": part.content
                }
            return dict_part

        def line_as_dict(line):
            return {
                "parts": [part_as_dict(part) for part in line.parts],
                "offset": line.offset
            }

        first = parameters.getQueryParameter("first", int, ValueError)
        last = parameters.getQueryParameter("last", int, ValueError)

        dict_lines = [line_as_dict(line) for line in value.getLines(first, last)]

        return parameters.filtered(
            "filecontents", {"lines": dict_lines})

    @staticmethod
    def multiple(parameters):
        """TODO: add documentation"""

        commit = jsonapi.deduce("v1/commits", parameters)
        if commit is None:
            raise jsonapi.UsageError(
                "commit must be specified, ex. &commit=<sha1>")

        file_obj = jsonapi.deduce("v1/files", parameters)

        blob_sha1 = commit.getFileInformation(file_obj).sha1

        return api.filecontent.fetch(
            parameters.critic, commit.repository, blob_sha1, file_obj)
