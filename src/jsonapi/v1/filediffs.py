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
class Filediffs(object):
    """Source code for a filechange"""

    name = "filediffs"
    contexts = (None, "changesets")
    value_class = api.filediff.Filediff
    exceptions = (api.filediff.FilediffError, api.filechange.FileChangeError)

    @staticmethod
    def json(value, parameters):
        """TODO: add documentation"""

        def part_as_dict(part):
            if not part.type and not part.state:
                return part.content
            dict_part = {
                "content": part.content
            }
            if part.type:
                dict_part["type"] = part.type
            if part.state:
                dict_part["state"] = part.state
            return dict_part

        def line_as_dict(line):
            dict_line = {
                "type": line.type_string,
                "old_offset": line.old_offset,
                "new_offset": line.new_offset,
            }
            dict_line["content"] = [part_as_dict(part) for
                                    part in line.content]
            return dict_line

        def chunk_as_dict(chunk):
            return {
                "content": [line_as_dict(line) for line in chunk.lines],
                "old_offset": chunk.old_offset,
                "old_count": chunk.old_count,
                "new_offset": chunk.new_offset,
                "new_count": chunk.new_count
            }

        context_lines = parameters.getQueryParameter(
            "context_lines", int, ValueError)
        if context_lines is not None:
            if context_lines < 0:
                raise jsonapi.UsageError(
                    "Negative number of context lines not supported")
        else:
            # TODO: load this from the user's config (or make it mandatory and
            # let the client handle config loading).
            context_lines = 3

        comment = jsonapi.deduce("v1/comments", parameters)
        if comment is not None:
            comments = [comment]
            ignore_chunks = True
        else:
            review = jsonapi.deduce("v1/reviews", parameters)
            if review is not None:
                comments = api.comment.fetchAll(
                    parameters.critic, review=review,
                    changeset=value.filechange.changeset)
            else:
                comments = None
            ignore_chunks = False

        macro_chunks = value.getMacroChunks(
            context_lines, comments, ignore_chunks)

        dict_chunks = [chunk_as_dict(chunk) for chunk in macro_chunks]
        return parameters.filtered(
            "filediffs", {
                "file": value.filechange,
                "changeset": value.filechange.changeset,
                "macro_chunks": dict_chunks,
                "old_count": value.old_count,
                "new_count": value.new_count
            })

    @staticmethod
    def single(parameters, argument):
        """TODO: add documentation"""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        if changeset is None:
            raise jsonapi.UsageError(
                "changeset needs to be specified, ex. &changeset=<id>")

        repository = jsonapi.deduce("v1/repositories", parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "repository needs to be specified, "
                "ex. &repository=<id or name>")

        file = api.file.fetch(parameters.critic, jsonapi.numeric_id(argument))
        filechange = api.filechange.fetch(parameters.critic, changeset, file)

        return api.filediff.fetch(parameters.critic, filechange)

    @staticmethod
    def multiple(parameters):
        """TODO: add documentation"""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        if changeset is None:
            raise jsonapi.UsageError(
                "changeset needs to be specified, ex. &changeset=<id>")

        repository = jsonapi.deduce("v1/repositories", parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "repository needs to be specified, "
                "ex. &repository=<id or name>")

        return api.filediff.fetchAll(parameters.critic, changeset)

    @staticmethod
    def resource_id(value):
        return value.filechange.file.id
