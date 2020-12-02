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
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic.gitaccess import SHA1
from critic import reviewing
from ..base import TransactionBase
from ..item import Delete, Insert, InsertMany, Update
from ..review import ReviewUserTag, has_unpublished_changes


async def reopen_issue(
    transaction: TransactionBase,
    issue: api.comment.Comment,
    new_location: Optional[api.comment.Location],
) -> None:
    critic = transaction.critic
    user = critic.effective_user

    if not isinstance(issue, api.comment.Issue):
        raise api.comment.Error("Only issues can be reopened")

    review = await issue.review
    if review.state in ("closed", "dropped"):
        raise api.comment.Error(f"Review is {review.state}")

    transaction.tables.add("commentchainchanges")

    ReviewUserTag.ensure(
        transaction,
        await issue.review,
        critic.effective_user,
        "unpublished",
        has_unpublished_changes,
    )

    draft_changes = await issue.draft_changes

    if draft_changes:
        new_state = draft_changes.new_state
        new_type = draft_changes.new_type
        if (new_state and new_state != "resolved") or new_type:
            raise api.comment.Error("Issue has unpublished conflicting modifications")

        if new_state == "resolved":
            await transaction.execute(
                Delete("commentchainchanges").where(
                    uid=user, chain=issue, to_state="closed"
                )
            )
            return

    if issue.state not in ("addressed", "resolved"):
        raise api.comment.Error("Only addressed/resolved issues can be reopened")

    to_state = "open"
    to_addressed_by = from_addressed_by = None

    if issue.state == "addressed":
        if new_location is None:
            raise api.comment.Error("Need new location to reopen addressed issue")

        new_location = new_location.as_file_version

        async with api.critic.Query[Tuple[SHA1, int, int]](
            critic,
            """SELECT sha1, first_line, last_line
                 FROM commentchainlines
                WHERE chain={issue}""",
            issue=issue,
        ) as result:
            existing_locations = {
                sha1: (first_line, last_line)
                async for sha1, first_line, last_line in result
            }

        if (await new_location.file_information).sha1 in existing_locations:
            raise api.comment.Error(
                "Invalid new location: file already present in file version"
            )

        propagation_result = await reviewing.comment.propagate.propagate_new_comment(
            await issue.review, new_location, existing_locations=existing_locations
        )

        from_state = "addressed"
        from_addressed_by = await issue.addressed_by
        to_addressed_by = propagation_result.addressed_by

        if to_addressed_by:
            to_state = "addressed"

        await transaction.execute(
            InsertMany(
                "commentchainlines",
                ["uid", "chain", "sha1", "first_line", "last_line"],
                [
                    dict(
                        uid=user,
                        chain=issue,
                        sha1=location.sha1,
                        first_line=location.first_line + 1,
                        last_line=location.last_line + 1,
                    )
                    for location in propagation_result.locations
                    if location.sha1 not in existing_locations
                ],
            )
        )

        if issue.is_draft:
            await transaction.execute(Update(issue).set(state=to_state))
            return
    else:
        from_state = "closed"

    await transaction.execute(
        Insert("commentchainchanges").values(
            uid=user,
            chain=issue,
            from_state=from_state,
            to_state=to_state,
            from_addressed_by=from_addressed_by,
            to_addressed_by=to_addressed_by,
        )
    )
