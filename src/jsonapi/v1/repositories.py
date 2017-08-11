# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

def from_argument(parameters, argument):
    repository_id, name = jsonapi.id_or_name(argument)
    return api.repository.fetch(
        parameters.critic, repository_id=repository_id, name=name)

@jsonapi.PrimaryResource
class Repositories(object):
    """The Git repositories on this system."""

    name = "repositories"
    value_class = api.repository.Repository
    exceptions = (api.repository.RepositoryError,)

    @staticmethod
    def json(value, parameters):
        """Repository {
             "id": integer, // the repository's id
             "name": string, // the repository's (unique) short name
             "path": string, // absolute file-system path
             "url": string, // the repository's URL
           }"""

        return parameters.filtered(
            "repositories", { "id": value.id,
                              "name": value.name,
                              "path": value.path,
                              "url": value.url })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) repositories on this system.

           REPOSITORY_ID : integer

           Retrieve a repository identified by its unique numeric id."""

        return Repositories.setAsContext(parameters, api.repository.fetch(
            parameters.critic, repository_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(parameters):
        """Retrieve a single named repository or all repositories on this
           system.

           name : SHORT_NAME : string

           Retrieve a repository identified by its unique short-name.  This is
           equivalent to accessing /api/v1/repositories/REPOSITORY_ID with that
           repository's numeric id.  When used, any other parameters are
           ignored.

           filter : highlighted : -

           If specified, retrieve only "highlighted" repositories.  These are
           repositories that are deemed of particular interest for the signed-in
           user.  (If no user is signed in, no repositories are highlighted.)"""

        name_parameter = parameters.getQueryParameter("name")
        if name_parameter:
            return api.repository.fetch(parameters.critic, name=name_parameter)
        filter_parameter = parameters.getQueryParameter("filter")
        if filter_parameter is not None:
            if filter_parameter == "highlighted":
                repositories = api.repository.fetchHighlighted(
                    parameters.critic)
            else:
                raise jsonapi.UsageError(
                    "Invalid repository filter parameter: %r"
                    % filter_parameter)
        else:
            repositories = api.repository.fetchAll(parameters.critic)
        return repositories

    @staticmethod
    def deduce(parameters):
        repository = parameters.context.get("repositories")
        repository_parameter = parameters.getQueryParameter("repository")
        if repository_parameter is not None:
            if repository is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: repository=%s"
                    % repository_parameter)
            repository = from_argument(parameters, repository_parameter)
        if repository is not None:
            return repository

        review = jsonapi.deduce("v1/reviews", parameters)
        if review is not None:
            return review.repository

    @staticmethod
    def fromParameter(value, parameters):
        repository_id, name = jsonapi.id_or_name(value)
        return api.repository.fetch(parameters.critic, repository_id, name=name)

    @staticmethod
    def setAsContext(parameters, repository):
        parameters.setContext(Repositories.name, repository)
        return repository
