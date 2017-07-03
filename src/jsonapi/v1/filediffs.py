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
    exceptions = (api.filediff.FilediffError, api.filechange.FilechangeError)

    @staticmethod
    def json(value, parameters):
        """TODO: add documentation"""

        def part_as_dict(part):
            dict_part = {
                "type": part.type,
                "content": part.content
                }
            if part.state is not None:
                dict_part["state"] = part.state
            return dict_part

        def line_as_dict(line):
            dict_line = {
                "type": line.type_string,
                "old_offset": line.old_offset,
                "new_offset": line.new_offset,
                }
            if line.old_content is not None:
                dict_line["old_content"] = [part_as_dict(part) for
                                            part in line.old_content]
            if line.new_content is not None:
                dict_line["new_content"] = [part_as_dict(part) for
                                            part in line.new_content]
            return dict_line

        def chunk_as_dict(chunk):
            return {
                "content": [line_as_dict(line) for line in chunk.lines],
                "old_offset": chunk.old_offset,
                "old_count": chunk.old_count,
                "new_offset": chunk.new_offset,
                "new_count": chunk.new_count
            }

        dict_chunks = [chunk_as_dict(chunk) for chunk in value.macro_chunks]
        return parameters.filtered(
            "filediffs", {
                "macro_chunks": dict_chunks,
                "old_count": value.old_count,
                "new_count": value.new_count,
                "id": value.id,
                "path": value.path,
                "changeset": value.changeset
            })

    @staticmethod
    def single(parameters, argument):
        """TODO: add documentation"""

        changeset = jsonapi.deduce("v1/changesets", parameters)
        if changeset is None:
            raise jsonapi.UsageError(
                "changeset needs to be specified, ex. &changeset=<id>")

        comment = jsonapi.deduce("v1/comments", parameters)
        ignore_chunks = comment is not None
        if comment is not None:
            comments = [comment]
        else:
            review = jsonapi.deduce("v1/reviews", parameters)
            if review is not None:
                comments = api.comment.fetchAll(
                    parameters.critic, review=review, changeset=changeset)
            else:
                comments = None

        repository = jsonapi.deduce("v1/repositories", parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "repository needs to be specified, "
                "ex. &repository=<id or name>")

        file_id = jsonapi.numeric_id(argument)
        filechange = api.filechange.fetch(parameters.critic, changeset, file_id)

        context_lines = parameters.getQueryParameter(
            "context_lines", int, ValueError)
        if context_lines_param is not None:
            if context_lines < 0:
                raise jsonapi.UsageError(
                    "Negative number of context lines not supported")
        else:
            # TODO: load this from the user's config (or make it mandatory and
            # let the client handle config loading).
            context_lines = 3

        return api.filediff.fetch(
            parameters.critic, repository, filechange, context_lines, comments,
            ignore_chunks=ignore_chunks)

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

        if filechange is not None:
            changeset = filechange.changeset

        review = jsonapi.deduce("v1/reviews", parameters)
        if review is not None:
            comments = api.comment.fetchAll(
                parameters.critic, review=review, changeset=changeset)
        else:
            comments = None

        context_lines = parameters.getQueryParameter("context_lines", int, ValueError)
        if context_lines_param is not None:
            if context_lines < 0:
                raise jsonapi.UsageError(
                    "Negative number of context lines not supported")
        else:
            # TODO: load this from the user's config (or make it mandatory and
            # let the client handle config loading).
            context_lines = 3

        if filechange is not None:
            filediff = api.filediff.fetch(
                parameters.critic, repository, filechange, context_lines, comments,
                ignore_chunks=ignore_chunks)
        else:
            filediff = api.filediff.fetchAll(
                parameters.critic, repository, changeset, context_lines, comments)
        return filediff
