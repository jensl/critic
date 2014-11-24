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

@jsonapi.PrimaryResource
class Reviews(object):
    """The reviews in this system."""

    name = "reviews"
    value_class = api.review.Review
    exceptions = (api.review.InvalidReviewId, api.repository.RepositoryError)

    @staticmethod
    def json(value, parameters, linked):
        """{
             "id": integer,
             "state": string,
             "summary": string,
             "description": string or null,
             "repository": integer,
             "branch": integer,
             "owners": integer[],
             "reviewers": integer[],
             "watchers": integer[],
             "commits": integer[],
           }"""
        owners_ids = set(owner.id for owner in value.owners)
        reviewers_ids = set(reviewer.id for reviewer in value.reviewers)
        watchers_ids = set(watcher.id for watcher in value.watchers)
        commits_ids = [commit.id for commit in value.commits]

        linked.add("branches", value.branch.id)
        linked.add("users", *(owners_ids | reviewers_ids | watchers_ids))
        linked.add("commits", *commits_ids)

        return parameters.filtered(
            "reviews", { "id": value.id,
                         "state": value.state,
                         "summary": value.summary,
                         "description": value.description,
                         "repository": value.repository.id,
                         "branch": value.branch.id,
                         "owners": sorted(owners_ids),
                         "reviewers": sorted(reviewers_ids),
                         "watchers": sorted(watchers_ids),
                         "commits": commits_ids })

    @staticmethod
    def single(critic, context, argument, parameters):
        """Retrieve one (or more) reviews in this system.

           REVIEW_ID : integer

           Retrieve a review identified by its unique numeric id."""

        return api.review.fetch(critic, review_id=jsonapi.numeric_id(argument))

    @staticmethod
    def multiple(critic, context, parameters):
        """Retrieve all reviews in this system.

           repository : REPOSITORY : -

           Include only reviews in one repository, identified by the
           repository's unique numeric id or short-name.

           state : STATE[,STATE,...] : -

           Include only reviews in the specified state.  Valid values are:
           <code>open</code>, <code>closed</code>, <code>dropped</code>."""

        repository = jsonapi.v1.repositories.Repositories.deduce(
            critic, context, parameters)
        state_parameter = parameters.getQueryParameter("state")
        if state_parameter:
            state = set(state_parameter.split(","))
            invalid = state - api.review.Review.STATE_VALUES
            if invalid:
                raise jsonapi.UsageError(
                    "Invalid review state values: %s"
                    % ", ".join(map(repr, sorted(invalid))))
        else:
            state = None
        return api.review.fetchAll(critic, repository=repository, state=state)
