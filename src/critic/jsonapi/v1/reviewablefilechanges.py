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

from typing import Collection, Sequence, Optional, Union, TypedDict

from critic import api
from critic import jsonapi

ReviewableFileChange = api.reviewablefilechange.ReviewableFileChange
DraftChanges = TypedDict(
    "DraftChanges", {"author": api.user.User, "new_is_reviewed": bool}
)


class ReviewableFileChanges(
    jsonapi.ResourceClass[ReviewableFileChange], api_module=api.reviewablefilechange
):
    """Reviewable file changes"""

    contexts = (None, "reviews", "changesets")

    @staticmethod
    async def json(
        parameters: jsonapi.Parameters, value: ReviewableFileChange
    ) -> jsonapi.JSONResult:
        """{
             "id": integer, // the object's unique id
             "review": integer,
             "changeset": integer,
             "file": integer,
             "deleted_lines": integer,
             "inserted_lines": integer,
             "is_reviewed": boolean,
             "reviewed_by": integer[],
             "assigned_reviewers": integer[],
             "draft_changes": DraftChanges or null,
           }

           DraftChanges {
             "author": integer, // author of draft changes
             "new_is_reviewed": boolean,
             "new_reviewed_by": integer,
           }"""

        async def reviewed_by() -> jsonapi.ValueWrapper[Collection[api.user.User]]:
            return await jsonapi.sorted_by_id(await value.reviewed_by)

        async def assigned_reviewers() -> jsonapi.ValueWrapper[
            Collection[api.user.User]
        ]:
            return await jsonapi.sorted_by_id(await value.assigned_reviewers)

        async def draft_changes() -> Optional[DraftChanges]:
            draft_changes = await value.draft_changes
            if draft_changes:
                return {
                    "author": draft_changes.author,
                    "new_is_reviewed": draft_changes.new_is_reviewed,
                }
            return None

        return {
            "id": value.id,
            "review": value.review,
            "changeset": value.changeset,
            "file": value.file,
            "scope": value.scope,
            "deleted_lines": value.deleted_lines,
            "inserted_lines": value.inserted_lines,
            "is_reviewed": value.is_reviewed,
            "reviewed_by": reviewed_by(),
            "assigned_reviewers": assigned_reviewers(),
            "draft_changes": draft_changes(),
        }

    @staticmethod
    async def single(
        parameters: jsonapi.Parameters, argument: str
    ) -> ReviewableFileChange:
        """Retrieve one (or more) reviewable file change.

           FILECHANGE_ID : integer

           Retrieve the reviewable changes to a file in a commit identified by
           its unique numeric id."""

        return await api.reviewablefilechange.fetch(
            parameters.critic, jsonapi.numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: jsonapi.Parameters,
    ) -> Sequence[ReviewableFileChange]:
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

        review = await Reviews.deduce(parameters)
        changeset = await Changesets.deduce(parameters)

        if not review:
            raise jsonapi.UsageError("Missing required parameter: review")

        file = await Files.fromParameter(parameters, "file")
        assignee = await Users.fromParameter(parameters, "assignee")
        state_parameter = parameters.getQueryParameter("state")

        if state_parameter is None:
            is_reviewed = None
        else:
            if state_parameter not in ("pending", "reviewed"):
                raise jsonapi.UsageError(
                    "Invalid parameter value: state=%r "
                    "(value values are 'pending' and 'reviewed')" % state_parameter
                )
            is_reviewed = state_parameter == "reviewed"

        return await api.reviewablefilechange.fetchAll(
            review,
            changeset=changeset,
            file=file,
            assignee=assignee,
            is_reviewed=is_reviewed,
        )

    @staticmethod
    async def update(
        parameters: jsonapi.Parameters,
        values: jsonapi.Values[ReviewableFileChange],
        data: jsonapi.JSONInput,
    ) -> None:
        critic = parameters.critic

        reviews = set([await filechange.review for filechange in values])
        if len(reviews) > 1:
            raise jsonapi.UsageError("Multiple reviews updated")
        review = reviews.pop()

        converted = await jsonapi.convert(
            parameters, {"draft_changes": {"new_is_reviewed": bool}}, data
        )
        is_reviewed = converted["draft_changes"]["new_is_reviewed"]

        async with api.transaction.start(critic) as transaction:
            modifier = transaction.modifyReview(review)

            if is_reviewed:
                for filechange in values:
                    await modifier.markChangeAsReviewed(filechange)
            else:
                for filechange in values:
                    await modifier.markChangeAsPending(filechange)

        await jsonapi.v1.batches.includeUnpublished(parameters, review)


from .changesets import Changesets
from .files import Files
from .reviews import Reviews
from .users import Users
