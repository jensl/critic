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
class Changesets(object):
    """Changesets in the git repositories"""

    name = "changesets"
    contexts = (None, "repositories", "reviews")
    value_class = api.changeset.Changeset
    exceptions = (api.changeset.ChangesetError,)

    @staticmethod
    def json(value, parameters):
        """Changeset {
             "id": integer, // the changeset's id
             "type": string, // the changeset type (direct, custom, merge, conflict)
             "from_commit": integer, // commit id for changesets from_commit
             "to_commit": integer, // commit id for changesets to_commit
             "files": File[], // a list of all files changed in this changeset
           }

           File {
               "id": integer, // the file's id
               "path": string, // the file's path
           }"""

        def files_as_json(files):
            if files is not None:
                return [{"id": file.id, "path": file.path} for file in files]
            else:
                return None

        return parameters.filtered(
            "changesets", { "id": value.id,
                            "type": value.type,
                            "from_commit": value.from_commit,
                            "to_commit": value.to_commit,
                            "files": files_as_json(value.files)})

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) changesets.

           CHANGESET_ID : integer

           Retrieve a changeset identified by its unique numeric id.

           repository : REPOSITORY : -

           Specify repository to access, identified by its unique numeric id or
           short-name.  Required unless a repository is specified in the
           resource path."""

        repository = jsonapi.deduce("v1/repositories", parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "repository needs to be specified, ex. &repository=<id>")
        return Changesets.setAsContext(parameters,
                                       api.changeset.fetch(
                                           parameters.critic,
                                           repository,
                                           jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(parameters):
        """Retrieve (and create if it doesn't exist) a changeset identified by
           a single commit (changeset type: direct) or any two commits in the
           same repository (changeset type: custom).

           from : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its from_commit. The SHA-1 sum can be abbreviated, but must be at
           least 4 characters long, and must be unambiguous in the repository.
           Must be used together with parameter 'to'.

           to : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its to_commit. The SHA-1 sum can be abbreviated, but must be at least
           4 characters long, and must be unambiguous in the repository. Must be
           used together with parameter 'from'.

           commit : COMMIT_SHA1 : string

           Retrieve a changeset with a commit (identified by its SHA-1 sum) as
           its to_commit, and the commit's parent as its from_commit. The SHA-1
           sum can be abbreviated, but must be at least 4 characters long, and
           must be unambiguous in the repository. Cannot be combined with 'from'
           or 'to'. Currently does not support merge commits.

           repository : REPOSITORY : -

           Specify repository to access, identified by its unique numeric id or
           short-name.  Required unless a repository is specified in the
           resource path."""

        repository = jsonapi.deduce("v1/repositories", parameters)

        from_param = parameters.getQueryParameter("from")
        to_param = parameters.getQueryParameter("to")
        single_param = parameters.getQueryParameter("commit")

        from_commit = None
        to_commit = None
        single_commit = None
        
        if from_param:
            from_commit = api.commit.fetch(repository, ref=from_param)
        if to_param:
            to_commit = api.commit.fetch(repository, ref=to_param)
        if single_param:
            single_commit = api.commit.fetch(repository, ref=single_param)

        if repository is None:
            raise jsonapi.UsageError("repository needs to be specified, ex. &repository=<id>")

        if not (from_commit or to_commit or single_commit):
            raise jsonapi.UsageError(
                "Missing required parameters from and to, or commit")
        if from_commit is None != to_commit is None:
            raise jsonapi.UsageError(
                "Missing required parameters from and to, only one supplied")

        if single_commit:
            return Changesets.setAsContext(
                parameters, api.changeset.fetch(
                    parameters.critic,
                    repository,
                    single_commit=single_commit))

        elif from_commit and to_commit:
            return Changesets.setAsContext(
                parameters, api.changeset.fetch(
                    parameters.critic,
                    repository,
                    from_commit=from_commit,
                    to_commit=to_commit))

        else:
            raise jsonapi.UsageError(
                "This should never happen")

    @staticmethod
    def deduce(parameters):
        repository = jsonapi.deduce("v1/repositories", parameters)
        changeset = parameters.context.get(Changesets.name)
        changeset_parameter = parameters.getQueryParameter("changeset")
        if changeset_parameter is not None:
            if changeset is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: changeset=%s"
                    % changeset_parameter)
            changeset_id = jsonapi.numeric_id(changeset_parameter)
            changeset = api.changeset.fetch(
                parameters.critic, repository, id=changeset_id)
        return changeset
            
        
    @staticmethod
    def setAsContext(parameters, changeset):
        parameters.setContext(Changesets.name, changeset)
        return changeset
