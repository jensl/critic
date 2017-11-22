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

from __future__ import annotations

import logging
from typing import Collection, Sequence, Optional, TypedDict, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import jsonapi

from ..utils import many


MorphedComment = TypedDict(
    "MorphedComment",
    {"comment": api.comment.Comment, "new_type": api.comment.CommentType},
)


class Batches(jsonapi.ResourceClass[api.batch.Batch], api_module=api.batch):
    """Batches of changes in reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: api.batch.Batch
    ) -> jsonapi.JSONResult:
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

        async def morphed_comments() -> Collection[MorphedComment]:
            return sorted(
                [
                    {"comment": comment, "new_type": new_type}
                    for comment, new_type in (await value.morphed_comments).items()
                ],
                key=lambda morphed_comment: morphed_comment["comment"].id,
            )

        return {
            "id": value.id,
            "is_empty": value.is_empty,
            "review": value.review,
            "author": value.author,
            "timestamp": jsonapi.v1.timestamp(value.timestamp),
            "comment": value.comment,
            "created_comments": jsonapi.sorted_by_id(lambda: value.created_comments),
            "written_replies": jsonapi.sorted_by_id(lambda: value.written_replies),
            "resolved_issues": jsonapi.sorted_by_id(lambda: value.resolved_issues),
            "reopened_issues": jsonapi.sorted_by_id(lambda: value.reopened_issues),
            "morphed_comments": morphed_comments(),
            "reviewed_changes": jsonapi.sorted_by_id(
                lambda: value.reviewed_file_changes
            ),
            "unreviewed_changes": jsonapi.sorted_by_id(
                lambda: value.unreviewed_file_changes
            ),
        }

    @staticmethod
    async def single(parameters: jsonapi.Parameters, argument: str) -> api.batch.Batch:
        """Retrieve one (or more) batches in reviews.

           BATCH_ID : integer

           Retrieve a batch identified by its unique numeric id."""

        batch = await api.batch.fetch(parameters.critic, jsonapi.numeric_id(argument))

        review = await Reviews.deduce(parameters)
        if review and review != batch.review:
            raise jsonapi.PathError("Batch does not belong to specified review")

        return batch

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Union[api.batch.Batch, Sequence[api.batch.Batch]]:
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

        review = await Reviews.deduce(parameters, required=True)
        author = await Users.fromParameter(parameters, "author")

        unpublished_parameter = parameters.getQueryParameter("unpublished")
        if unpublished_parameter is not None:
            if unpublished_parameter == "yes":
                if author is not None:
                    raise jsonapi.UsageError(
                        "Parameters 'author' and 'unpublished' cannot be " "combined"
                    )
                return await api.batch.fetchUnpublished(review)
            else:
                raise jsonapi.UsageError(
                    "Invalid 'unpublished' parameter: %r (must be 'yes')"
                    % unpublished_parameter
                )

        return await api.batch.fetchAll(critic, review=review, author=author)

    @staticmethod
    async def create(
        parameters: jsonapi.Parameters, data: jsonapi.JSONInput
    ) -> api.batch.Batch:
        critic = parameters.critic

        converted = await jsonapi.convert(
            parameters, {"review?": api.review.Review, "comment?": str}, data
        )

        review = await Reviews.deduce(parameters)

        if not review:
            if "review" not in converted:
                raise jsonapi.UsageError.missingInput("review")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise jsonapi.UsageError("Conflicting reviews specified")

        assert review

        if "comment" in converted:
            comment_text = converted["comment"].strip()
            if not comment_text:
                raise jsonapi.UsageError("Empty comment specified")
        else:
            comment_text = None

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyReview(review)
            note: Optional[api.transaction.comment.CreatedComment]

            if comment_text:
                note = (
                    await modifier.createComment(
                        comment_type="note",
                        author=critic.effective_user,
                        text=comment_text,
                    )
                ).created
            else:
                note = None

            created_batch = await modifier.submitChanges(note)

        logger.debug("created batch")

        return await created_batch

    @staticmethod
    async def delete(
        parameters: jsonapi.Parameters, values: jsonapi.Values[api.batch.Batch]
    ) -> None:
        critic = parameters.critic

        discard = parameters.getQueryParameter(
            "discard", converter=many(api.batch.as_discard_value)
        )
        if discard is None:
            raise jsonapi.UsageError.missingParameter("discard")
        if not discard:
            raise jsonapi.UsageError.invalidParameter(
                "discard", message="Must specify at least one category"
            )

        for batch in values:
            if batch.id is not None:
                raise jsonapi.UsageError("Only draft changes can be deleted")

        async with api.transaction.start(critic) as transaction:
            for batch in values:
                modifier = transaction.modifyReview(await batch.review)
                await modifier.discardChanges(discard)

    @staticmethod
    async def deduce(parameters: jsonapi.Parameters) -> Optional[api.batch.Batch]:
        batch = parameters.context.get("batches")
        batch_parameter = parameters.getQueryParameter("batch")
        if batch_parameter is not None:
            if batch is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: batch=%s" % batch_parameter
                )
            batch = await api.batch.fetch(
                parameters.critic, jsonapi.numeric_id(batch_parameter)
            )
        return batch

    @staticmethod
    async def setAsContext(
        parameters: jsonapi.Parameters, batch: api.batch.Batch
    ) -> None:
        parameters.setContext(Batches.name, batch)


async def includeUnpublished(
    parameters: jsonapi.Parameters, review: api.review.Review
) -> None:
    if parameters.critic.actual_user and "batches" in parameters.include:
        logger.debug(
            "including unpublished batch for %s", parameters.critic.actual_user.name
        )
        parameters.addLinked(await api.batch.fetchUnpublished(review))


from .reviews import Reviews
from .users import Users
