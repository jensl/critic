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

from typing import Sequence, Optional, TypedDict

from critic import api
from ..check import convert
from ..exceptions import UsageError
from ..resourceclass import ResourceClass
from ..parameters import Parameters
from ..types import JSONInput, JSONResult
from ..utils import numeric_id, sorted_by_id
from ..values import Values
from ..valuewrapper import ValueWrapper

ReviewableFileChange = api.reviewablefilechange.ReviewableFileChange
DraftChanges = TypedDict(
    "DraftChanges", {"author": api.user.User, "new_is_reviewed": bool}
)


class ReviewableFileChanges(
    ResourceClass[ReviewableFileChange], api_module=api.reviewablefilechange
):
    """Reviewable file changes"""

    contexts = (None, "reviews", "changesets")

    @staticmethod
    async def json(parameters: Parameters, value: ReviewableFileChange) -> JSONResult:
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

        async def reviewed_by() -> ValueWrapper[Sequence[api.user.User]]:
            return await sorted_by_id(await value.reviewed_by)

        async def assigned_reviewers() -> ValueWrapper[Sequence[api.user.User]]:
            return await sorted_by_id(await value.assigned_reviewers)

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

    @classmethod
    async def single(
        cls, parameters: Parameters, argument: str
    ) -> ReviewableFileChange:
        """Retrieve one (or more) reviewable file change.

        FILECHANGE_ID : integer

        Retrieve the reviewable changes to a file in a commit identified by
        its unique numeric id."""

        return await api.reviewablefilechange.fetch(
            parameters.critic, numeric_id(argument)
        )

    @staticmethod
    async def multiple(
        parameters: Parameters,
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

        review = await parameters.deduce(api.review.Review)
        changeset = await parameters.deduce(api.changeset.Changeset)

        if not review:
            raise UsageError("Missing required parameter: review")

        file = await parameters.fromParameter(api.file.File, "file")
        assignee = await parameters.fromParameter(api.user.User, "assignee")
        state_parameter = parameters.query.get("state")

        if state_parameter is None:
            is_reviewed = None
        else:
            if state_parameter not in ("pending", "reviewed"):
                raise UsageError(
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

    @classmethod
    async def update(
        cls,
        parameters: Parameters,
        values: Values[ReviewableFileChange],
        data: JSONInput,
    ) -> None:
        critic = parameters.critic

        reviews = set([await filechange.review for filechange in values])
        if len(reviews) > 1:
            raise UsageError("Multiple reviews updated")
        review = reviews.pop()

        converted = await convert(
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

        await includeUnpublished(parameters, review)


from .batches import includeUnpublished
