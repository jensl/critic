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

from . import ReviewUserTag, has_unpublished_changes
from .. import Transaction, Query, Insert

from critic import api


async def mark_change_as_reviewed(
    transaction: Transaction, rfc: api.reviewablefilechange.ReviewableFileChange
) -> None:
    critic = transaction.critic

    draft_changes = await rfc.draft_changes
    if draft_changes and draft_changes.new_is_reviewed:
        raise api.reviewablefilechange.Error(
            "Specified file change is already marked as reviewed",
            code="ALREADY_REVIEWED",
        )

    reviewed_by = await rfc.reviewed_by
    if critic.effective_user in reviewed_by:
        raise api.reviewablefilechange.Error(
            "Specified file change is already marked as reviewed",
            code="ALREADY_REVIEWED",
        )

    if critic.effective_user not in await rfc.assigned_reviewers:
        raise api.reviewablefilechange.Error(
            "Specified file change is not assigned to current user", code="NOT_ASSIGNED"
        )

    transaction.tables.add("reviewfilechanges")

    if draft_changes:
        transaction.items.append(
            Query(
                """DELETE
                     FROM reviewfilechanges
                    WHERE file={file}
                      AND uid={user}
                      AND NOT to_reviewed""",
                file=rfc,
                user=critic.effective_user,
            )
        )

    if critic.effective_user not in reviewed_by:
        transaction.items.append(
            Insert("reviewfilechanges").values(
                file=rfc,
                uid=critic.effective_user,
                from_reviewed=False,
                to_reviewed=True,
            )
        )

    ReviewUserTag.ensure(
        transaction,
        await rfc.review,
        critic.effective_user,
        "unpublished",
        has_unpublished_changes,
    )
