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
    lists = ("issues", "notes")

    @staticmethod
    def json(value, parameters):
        """Review {
             "id": integer,
             "state": string,
             "summary": string,
             "description": string or null,
             "repository": integer,
             "branch": integer,
             "owners": integer[],
             "active_reviewers": integer[],
             "assigned_reviewers": integer[],
             "watchers": integer[],
             "partitions": Partition[],
             "issues": integer[],
             "notes": integer[],
             "pending_rebase": integer or null,
             "progress": float,
             "progress_per_commit": CommitChangeCount[],
           }

           Partition {
             "commits": integer[],
             "rebase": integer or null,
           }

           CommitChangeCount {
             "commit_id": integer,
             "total_changes": integer,
             "reviewed_changes": integer,
           }"""

        def change_counts_as_dict(change_counts):
            return [{
                "commit_id": change_count.commit_id,
                "total_changes": change_count.total_changes,
                "reviewed_changes": change_count.reviewed_changes,
                } for change_count in change_counts]

        partitions = []

        def add_partition(partition):
            if partition.following:
                partition_rebase = partition.following.rebase
            else:
                partition_rebase = None

            partitions.append({ "commits": list(partition.commits.topo_ordered),
                                "rebase": partition_rebase })

            if partition.following:
                add_partition(partition.following.partition)

        add_partition(value.first_partition)

        return parameters.filtered(
            "reviews", { "id": value.id,
                         "state": value.state,
                         "summary": value.summary,
                         "description": value.description,
                         "repository": value.repository,
                         "branch": value.branch,
                         "owners": jsonapi.sorted_by_id(value.owners),
                         "active_reviewers": jsonapi.sorted_by_id(
                             value.active_reviewers),
                         "assigned_reviewers": jsonapi.sorted_by_id(
                             value.assigned_reviewers),
                         "watchers": jsonapi.sorted_by_id(value.watchers),
                         "partitions": partitions,
                         "issues": jsonapi.sorted_by_id(value.issues),
                         "notes": jsonapi.sorted_by_id(value.notes),
                         "pending_rebase": value.pending_rebase,
                         "progress": value.total_progress,
                         "progress_per_commit":
                             change_counts_as_dict(value.progress_per_commit)})

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) reviews in this system.

           REVIEW_ID : integer

           Retrieve a review identified by its unique numeric id."""

        return Reviews.setAsContext(parameters, api.review.fetch(
            parameters.critic, review_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(parameters):
        """Retrieve all reviews in this system.

           repository : REPOSITORY : -

           Include only reviews in one repository, identified by the
           repository's unique numeric id or short-name.

           state : STATE[,STATE,...] : -

           Include only reviews in the specified state.  Valid values are:
           <code>open</code>, <code>closed</code>, <code>dropped</code>."""

        repository = jsonapi.deduce("v1/repositories", parameters)
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
        return api.review.fetchAll(
            parameters.critic, repository=repository, state=state)

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        path = parameters.subresource_path
        review = value

        if review:
            if path == ["issues"] or path == ["notes"]:
                Reviews.setAsContext(parameters, review)
                if path == ["issues"]:
                    comment_type = "issue"
                else:
                    comment_type = "note"
                jsonapi.ensure(data, "type", comment_type)
                raise jsonapi.InternalRedirect("v1/comments")

        raise jsonapi.UsageError("Review creation not yet supported")

    @staticmethod
    def deduce(parameters):
        review = parameters.context.get("reviews")
        review_parameter = parameters.getQueryParameter("review")
        if review_parameter is not None:
            if review is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: review=%s" % review_parameter)
            review = api.review.fetch(
                parameters.critic,
                review_id=jsonapi.numeric_id(review_parameter))
        return review

    @staticmethod
    def setAsContext(parameters, review):
        parameters.setContext(Reviews.name, review)
        # Also set the review's repository and branch as context.
        jsonapi.v1.repositories.Repositories.setAsContext(
            parameters, review.repository)
        jsonapi.v1.branches.Branches.setAsContext(parameters, review.branch)
        return review
