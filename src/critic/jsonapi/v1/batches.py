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
from ..check import convert
from ..exceptions import PathError, UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import many, numeric_id, sorted_by_id
from ..values import Values
from .timestamp import timestamp


MorphedComment = TypedDict(
    "MorphedComment",
    {"comment": api.comment.Comment, "new_type": api.comment.CommentType},
)


class Batches(ResourceClass[api.batch.Batch], api_module=api.batch):
    """Batches of changes in reviews."""

    contexts = (None, "reviews")

    @staticmethod
    async def json(parameters: Parameters, value: api.batch.Batch) -> JSONResult:
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
                    MorphedComment(comment=comment, new_type=new_type)
                    for comment, new_type in (await value.morphed_comments).items()
                ],
                key=lambda morphed_comment: morphed_comment["comment"].id,
            )

        return {
            "id": value.id,
            "is_empty": value.is_empty,
            "review": value.review,
            "author": value.author,
            "timestamp": timestamp(value.timestamp),
            "comment": value.comment,
            "created_comments": sorted_by_id(lambda: value.created_comments),
            "written_replies": sorted_by_id(lambda: value.written_replies),
            "resolved_issues": sorted_by_id(lambda: value.resolved_issues),
            "reopened_issues": sorted_by_id(lambda: value.reopened_issues),
            "morphed_comments": morphed_comments(),
            "reviewed_changes": sorted_by_id(lambda: value.reviewed_file_changes),
            "unreviewed_changes": sorted_by_id(lambda: value.unreviewed_file_changes),
        }

    @classmethod
    async def single(cls, parameters: Parameters, argument: str) -> api.batch.Batch:
        """Retrieve one (or more) batches in reviews.

        BATCH_ID : integer

        Retrieve a batch identified by its unique numeric id."""

        batch = await api.batch.fetch(parameters.critic, numeric_id(argument))

        review = await parameters.deduce(api.review.Review)
        if review and review != batch.review:
            raise PathError("Batch does not belong to specified review")

        return batch

    @staticmethod
    async def multiple(
        parameters: Parameters,
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

        review = await parameters.deduce(api.review.Review)
        if not review:
            raise UsageError.missingParameter("review")
        author = await parameters.fromParameter(api.user.User, "author")

        unpublished_parameter = parameters.query.get("unpublished")
        if unpublished_parameter is not None:
            if unpublished_parameter == "yes":
                if author is not None:
                    raise UsageError(
                        "Parameters 'author' and 'unpublished' cannot be " "combined"
                    )
                return await api.batch.fetchUnpublished(review)
            else:
                raise UsageError(
                    "Invalid 'unpublished' parameter: %r (must be 'yes')"
                    % unpublished_parameter
                )

        return await api.batch.fetchAll(critic, review=review, author=author)

    @staticmethod
    async def create(parameters: Parameters, data: JSONInput) -> api.batch.Batch:
        critic = parameters.critic

        converted = await convert(
            parameters, {"review?": api.review.Review, "comment?": str}, data
        )

        review = await parameters.deduce(api.review.Review)

        if not review:
            if "review" not in converted:
                raise UsageError.missingInput("review")
            review = converted["review"]
        elif "review" in converted and review != converted["review"]:
            raise UsageError("Conflicting reviews specified")

        assert review

        if "comment" in converted:
            comment_text = converted["comment"].strip()
            if not comment_text:
                raise UsageError("Empty comment specified")
        else:
            comment_text = None

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyReview(review)
            note: Optional[api.comment.Comment]

            if comment_text:
                note = (
                    await modifier.createComment(
                        comment_type="note",
                        author=critic.effective_user,
                        text=comment_text,
                    )
                ).subject
            else:
                note = None

            return await modifier.submitChanges(note)

    @classmethod
    async def delete(
        cls, parameters: Parameters, values: Values[api.batch.Batch]
    ) -> None:
        critic = parameters.critic

        discard = parameters.query.get(
            "discard", converter=many(api.batch.as_discard_value)
        )
        if discard is None:
            raise UsageError.missingParameter("discard")
        if not discard:
            raise UsageError.invalidParameter(
                "discard", message="Must specify at least one category"
            )

        for batch in values:
            if batch.id is not None:
                raise UsageError("Only draft changes can be deleted")

        async with api.transaction.start(critic) as transaction:
            for batch in values:
                modifier = transaction.modifyReview(await batch.review)
                await modifier.discardChanges(discard)

    @classmethod
    async def deduce(cls, parameters: Parameters) -> Optional[api.batch.Batch]:
        batch = parameters.in_context(api.batch.Batch)
        batch_parameter = parameters.query.get("batch")
        if batch_parameter is not None:
            if batch is not None:
                raise UsageError(
                    "Redundant query parameter: batch=%s" % batch_parameter
                )
            batch = await api.batch.fetch(
                parameters.critic, numeric_id(batch_parameter)
            )
        return batch


async def includeUnpublished(parameters: Parameters, review: api.review.Review) -> None:
    if parameters.critic.actual_user and "batches" in parameters.include:
        logger.debug(
            "including unpublished batch for %s", parameters.critic.actual_user.name
        )
        parameters.addLinked(await api.batch.fetchUnpublished(review))
