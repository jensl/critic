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
from .updatewouldbeacceptedtag import UpdateWouldBeAcceptedTag
from ..item import Delete, Insert
from ..modifier import Modifier


async def mark_change_as_pending(
    modifier: Modifier[api.review.Review],
    rfc: api.reviewablefilechange.ReviewableFileChange,
) -> None:
    transaction = modifier.transaction
    critic = transaction.critic

    draft_changes = await rfc.draft_changes
    reviewed_by = await rfc.reviewed_by

    if draft_changes:
        if not draft_changes.new_is_reviewed:
            raise api.reviewablefilechange.Error(
                "Specified file change is already marked as pending",
                code="ALREADY_PENDING",
            )
    elif critic.effective_user not in reviewed_by:
        raise api.reviewablefilechange.Error(
            "Specified file change is already marked as pending", code="ALREADY_PENDING"
        )

    transaction.tables.add("reviewfilechanges")

    if draft_changes:
        await transaction.execute(
            Delete("reviewfilechanges").where(
                file=rfc, uid=critic.effective_user, to_reviewed=True
            )
        )

    if critic.effective_user in reviewed_by:
        await transaction.execute(
            Insert("reviewfilechanges").values(
                file=rfc,
                uid=critic.effective_user,
                from_reviewed=True,
                to_reviewed=False,
            )
        )

    ReviewUserTag.ensure(
        transaction,
        await rfc.review,
        critic.effective_user,
        "unpublished",
        has_unpublished_changes,
    )

    transaction.finalizers.add(UpdateWouldBeAcceptedTag(modifier))
