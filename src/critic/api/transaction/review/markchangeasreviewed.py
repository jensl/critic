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

logger = logging.getLogger(__name__)

from critic import api
from . import ReviewUserTag, has_unpublished_changes
from .updatereviewtags import UpdateReviewTags
from .updatewouldbeacceptedtag import UpdateWouldBeAcceptedTag
from ..base import TransactionBase
from ..item import Delete, Insert
from ..modifier import Modifier


async def mark_change_as_reviewed(
    transaction: TransactionBase,
    rfc: api.reviewablefilechange.ReviewableFileChange,
) -> None:
    critic = transaction.critic

    review = await rfc.review
    draft_changes = await rfc.draft_changes
    reviewed_by = await rfc.reviewed_by

    if draft_changes:
        if draft_changes.new_is_reviewed:
            raise api.reviewablefilechange.Error(
                "Specified file change is already marked as reviewed",
                code="ALREADY_REVIEWED",
            )
    elif critic.effective_user in reviewed_by:
        raise api.reviewablefilechange.Error(
            "Specified file change is already marked as reviewed",
            code="ALREADY_REVIEWED",
        )

    if critic.effective_user not in await rfc.assigned_reviewers:
        raise api.reviewablefilechange.Error(
            "Specified file change is not assigned to current user", code="NOT_ASSIGNED"
        )

    transaction.tables.add("reviewuserfilechanges")

    if draft_changes:
        logger.debug("%r: unmarking as reviewed", rfc)
        await transaction.execute(
            Delete("reviewuserfilechanges").where(
                file=rfc, uid=critic.effective_user, to_reviewed=False
            )
        )

    if critic.effective_user not in reviewed_by:
        logger.debug("%r: marking as reviewed", rfc)
        await transaction.execute(
            Insert("reviewuserfilechanges").values(
                file=rfc,
                uid=critic.effective_user,
                from_reviewed=False,
                to_reviewed=True,
            )
        )

    ReviewUserTag.ensure(
        transaction,
        review,
        critic.effective_user,
        "unpublished",
        has_unpublished_changes,
    )

    transaction.finalizers.add(UpdateWouldBeAcceptedTag(review))
    transaction.finalizers.add(UpdateReviewTags(review))
