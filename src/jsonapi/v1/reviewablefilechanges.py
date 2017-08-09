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
class ReviewableFileChanges(object):
    """Reviewable file changes"""

    name = "reviewablefilechanges"
    contexts = (None, "reviews", "changesets")
    value_class = api.reviewablefilechange.ReviewableFileChange
    exceptions = api.reviewablefilechange.ReviewableFileChangeError

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer, // the object's unique id
             "review": integer,
             "changeset": integer,
             "file": integer,
             "deleted_lines": integer,
             "inserted_lines": integer,
             "is_reviewed": boolean,
             "reviewed_by": integer,
             "assigned_reviewers": integer[],
             "draft_changes": DraftChanges or null,
           }

           DraftChanges {
             "author": integer, // author of draft changes
             "new_is_reviewed": boolean,
             "new_reviewed_by": integer,
           }"""

        draft_changes = value.draft_changes
        if draft_changes:
            draft_changes_json = {
                "author": draft_changes.author,
                "new_is_reviewed": draft_changes.new_is_reviewed,
                "new_reviewed_by": draft_changes.new_reviewed_by,
            }
        else:
            draft_changes_json = None

        return parameters.filtered(
            "reviewablefilechanges", {
                "id": value.id,
                "review": value.review,
                "changeset": value.changeset,
                "file": value.file,
                "deleted_lines": value.deleted_lines,
                "inserted_lines": value.inserted_lines,
                "is_reviewed": value.is_reviewed,
                "reviewed_by": value.reviewed_by,
                "assigned_reviewers": jsonapi.sorted_by_id(
                    value.assigned_reviewers),
                "draft_changes": draft_changes_json,
            })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) reviewable file change.

           FILECHANGE_ID : integer

           Retrieve the reviewable changes to a file in a commit identified by
           its unique numeric id."""

        return api.reviewablefilechange.fetch(
            parameters.critic, jsonapi.numeric_id(argument))

    @staticmethod
    def multiple(parameters):
        """Retrieve all reviewable file changes in a review.

           review : REVIEW_ID : -

           Retrieve the reviewable changes in the specified review.

           changeset : CHANGESET_ID : -

           Retrieve the reviewable changes in the specified changeset.

           file : FILE : -

           Retrieve the reviewable changes in the specified file only.

           assignee : USER : -

           Retrieve reviewable changes assigned to the specified user only.

           state : STATE : "pending" or "reviewed"

           Retrieve reviewable changes in the specified state only."""

        review = jsonapi.deduce("v1/reviews", parameters)
        changeset = jsonapi.deduce("v1/changesets", parameters)

        if not review:
            raise jsonapi.UsageError("Missing required parameter: review")

        file = jsonapi.from_parameter("v1/files", "file", parameters)
        assignee = jsonapi.from_parameter("v1/users", "assignee", parameters)
        state_parameter = parameters.getQueryParameter("state")

        if state_parameter is None:
            is_reviewed = None
        else:
            if state_parameter not in ("pending", "reviewed"):
                raise jsonapi.UsageError(
                    "Invalid parameter value: state=%r "
                    "(value values are 'pending' and 'reviewed')"
                    % state_parameter)
            is_reviewed = state_parameter == "reviewed"

        return api.reviewablefilechange.fetchAll(
            parameters.critic, review, changeset, file, assignee, is_reviewed)

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic
        filechanges = [value] if value else values

        reviews = set(filechange.review for filechange in filechanges)
        if len(reviews) > 1:
            raise jsonapi.UsageError("Multiple reviews updated")
        review = reviews.pop()

        converted = jsonapi.convert(
            parameters,
            {
                "draft_changes": {
                    "new_is_reviewed": bool,
                },
            },
            data)

        is_reviewed = converted["draft_changes"]["new_is_reviewed"]

        with api.transaction.Transaction(critic) as transaction:
            modifier = transaction \
                .modifyReview(review)

            if is_reviewed:
                for filechange in filechanges:
                    modifier.markChangeAsReviewed(filechange)
            else:
                for filechange in filechanges:
                    modifier.markChangeAsPending(filechange)
