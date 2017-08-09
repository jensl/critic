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
class Batches(object):
    """Batches of changes in reviews."""

    name = "batches"
    contexts = (None, "reviews")
    value_class = api.batch.Batch
    exceptions = api.batch.BatchError

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer or null,
             "is_empty": boolean,
             "review": integer,
             "author": integer,
             "comment": integer or null,
             "timestamp": float or null,
             "created_comments": integer[],
             "written_replies": integer[],
             "resolved_issues": integer[],
             "reopened_issues": integer[],
             "morphed_comments": MorphedComment[],
             "reviewed_changes": integer[],
             "unreviewed_changes": integer[],
           }

           MorphedComment {
             "comment": integer,
             "new_type": "issue" or "note",
           }"""

        morphed_comments = sorted([
            { "comment": comment, "new_type": new_type }
            for comment, new_type in value.morphed_comments.items()
        ], key=lambda morphed_comment: morphed_comment["comment"].id)

        timestamp = jsonapi.v1.timestamp(value.timestamp)
        return parameters.filtered(
            "batches", { "id": value.id,
                         "is_empty": value.is_empty,
                         "review": value.review,
                         "author": value.author,
                         "timestamp": timestamp,
                         "comment": value.comment,
                         "created_comments": jsonapi.sorted_by_id(
                             value.created_comments),
                         "written_replies": jsonapi.sorted_by_id(
                             value.written_replies),
                         "resolved_issues": jsonapi.sorted_by_id(
                             value.resolved_issues),
                         "reopened_issues": jsonapi.sorted_by_id(
                             value.reopened_issues),
                         "morphed_comments": morphed_comments,
                         "reviewed_changes": jsonapi.sorted_by_id(
                             value.reviewed_file_changes),
                         "unreviewed_changes": jsonapi.sorted_by_id(
                             value.unreviewed_file_changes) })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) batches in reviews.

           BATCH_ID : integer

           Retrieve a batch identified by its unique numeric id."""

        batch = api.batch.fetch(
            parameters.critic, batch_id=jsonapi.numeric_id(argument))

        review = jsonapi.deduce("v1/reviews", parameters)
        if review and review != batch.review:
            raise jsonapi.PathError(
                "Batch does not belong to specified review")

        return Batches.setAsContext(parameters, batch)

    @staticmethod
    def multiple(parameters):
        """Retrieve all batches in the system (or review.)

           review : REVIEW_ID : integer

           Retrieve only batches in the specified review.  Can only be used if a
           review is not specified in the resource path.

           author : AUTHOR : integer or string

           Retrieve only batches authored by the specified user, identified by
           the user's unique numeric id or user name.

           unpublished : UNPUBLISHED : 'yes'

           Retrieve a single batch representing the current user's unpublished
           changes to a review. Must be combined with `review` and cannot be
           combined with `author`."""

        critic = parameters.critic

        review = jsonapi.deduce("v1/reviews", parameters)
        author = jsonapi.from_parameter("v1/users", "author", parameters)

        unpublished_parameter = parameters.getQueryParameter("unpublished")
        if unpublished_parameter is not None:
            if unpublished_parameter == "yes":
                if author is not None:
                    raise jsonapi.UsageError(
                        "Parameters 'author' and 'unpublished' cannot be "
                        "combined")
                return api.batch.fetchUnpublished(critic, review)
            else:
                raise jsonapi.UsageError(
                    "Invalid 'unpublished' parameter: %r (must be 'yes')"
                    % unpublished_parameter)

        return api.batch.fetchAll(critic, review=review, author=author)

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)

        if value or values:
            raise jsonapi.UsageError("Invalid POST request")

        converted = jsonapi.convert(
            parameters,
            {
                "review?": api.review.Review,
                "comment?": str,
            },
            data)

        review = jsonapi.deduce("v1/reviews", parameters)

        if not review:
            if "review" not in converted:
                raise jsonapi.UsageError("No review specified")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise jsonapi.UsageError("Conflicting reviews specified")

        if "comment" in converted:
            comment_text = converted["comment"].strip()
            if not comment_text:
                raise jsonapi.UsageError("Empty comment specified")
        else:
            comment_text = None

        result = []

        def collectBatch(batch):
            assert isinstance(batch, api.batch.Batch)
            result.append(batch)

        with api.transaction.Transaction(critic) as transaction:
            modifier = transaction.modifyReview(review)

            if comment_text:
                note = modifier.createComment(comment_type="note",
                                              author=critic.actual_user,
                                              text=comment_text)
            else:
                note = None

            modifier.submitChanges(note, callback=collectBatch)

        assert len(result) == 1
        return result[0], None

    @staticmethod
    def deduce(parameters):
        batch = parameters.context.get("batches")
        batch_parameter = parameters.getQueryParameter("batch")
        if batch_parameter is not None:
            if batch is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: batch=%s" % batch_parameter)
            batch = api.batch.fetch(
                parameters.critic, jsonapi.numeric_id(batch_parameter))
        return batch

    @staticmethod
    def setAsContext(parameters, batch):
        parameters.setContext(Batches.name, batch)
        return batch
