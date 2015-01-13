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

import datetime
import re

EPOCH = datetime.datetime.utcfromtimestamp(0)

import api
import jsonapi

@jsonapi.PrimaryResource
class Commits(object):
    """Commits in the Git repositories."""

    name = "commits"
    contexts = (None, "repositories")
    value_class = api.commit.Commit
    exceptions = (api.commit.CommitError,)

    @staticmethod
    def json(value, parameters, linked):
        """{
             "id": integer, // the commit's id
             "sha1": string, // the commit's SHA-1 sum
             "summary": string, // (processed) commit summary
             "message": string, // full / raw commit message
             "parents": [integer], // list of commit ids
             "author": {
               "name": string, // author (full)name
               "email": string, // author email
               "timestamp": float, // seconds since epoch
             },
             "committer": {
               "name": string, // committer (full)name
               "email": string, // committer email
               "timestamp": float, // seconds since epoch
             },
           }"""

        parents_ids = [parent.id for parent in value.parents]

        # Note: We're not adding parent commits to |linked| here.  Doing so
        # would typically lead to recursively dumping all commits in a
        # repository a lot of the time, which wouldn't generally be useful.
        #
        # Instead, we'll add commits as linked resources when a different type
        # of resource, e.g. a review, references a more limited set of commits.

        def userAndTimestamp(user_and_timestamp):
            timestamp_delta = (user_and_timestamp.timestamp - EPOCH)
            return { "name": user_and_timestamp.name,
                     "email": user_and_timestamp.email,
                     "timestamp": timestamp_delta.total_seconds() }

        return parameters.filtered(
            "branches", { "id": value.id,
                          "sha1": value.sha1,
                          "summary": value.summary,
                          "message": value.message,
                          "parents": parents_ids,
                          "author": userAndTimestamp(value.author),
                          "committer": userAndTimestamp(value.committer) })

    @staticmethod
    def single(critic, argument, parameters):
        """Retrieve one (or more) commits from a Git repository.

           COMMIT_ID : integer

           Retrieve a commit identified by its unique numeric id.

           repository : REPOSITORY : -

           Specify repository to access, identified by its unique numeric id or
           short-name.  Required unless a repository is specified in the
           resource path."""

        repository = jsonapi.v1.repositories.Repositories.deduce(
            critic, parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "Commit reference must have repository specified.")
        return Commits.setAsContext(parameters, api.commit.fetch(
            repository, commit_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(critic, parameters):
        """Retrieve a single commit identified by its SHA-1 sum.

           sha1 : COMMIT_SHA1 : string

           Retrieve a commit identified by its SHA-1 sum.  The SHA-1 sum can be
           abbreviated, but must be at least 4 characters long, and must be
           unambigious in the repository.

           repository : REPOSITORY : -

           Specify repository to access, identified by its unique numeric id or
           short-name.  Required unless a repository is specified in the
           resource path."""

        sha1_parameter = parameters.getQueryParameter("sha1")
        if sha1_parameter is None:
            raise jsonapi.UsageError("Missing required SHA-1 parameter.")
        if not re.match("[0-9A-Fa-f]{4,40}$", sha1_parameter):
            raise jsonapi.UsageError(
                "Invalid SHA-1 parameter: %r" % sha1_parameter)
        repository = jsonapi.v1.repositories.Repositories.deduce(
            critic, parameters)
        if repository is None:
            raise jsonapi.UsageError(
                "Commit reference must have repository specified.")
        return api.commit.fetch(repository, sha1=sha1_parameter)

    @staticmethod
    def setAsContext(parameters, commit):
        parameters.setContext(Commits.name, commit)
        return commit
