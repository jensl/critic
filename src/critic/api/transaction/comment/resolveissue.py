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

from ..base import TransactionBase
from ..item import Delete, Insert
from ..review.updateunpublishedtag import UpdateUnpublishedTag
from ..review.updatewouldbeacceptedtag import UpdateWouldBeAcceptedTag
from critic import api


async def resolve_issue(
    transaction: TransactionBase, issue: api.comment.Comment
) -> None:
    critic = transaction.critic

    if not isinstance(issue, api.comment.Issue):
        raise api.comment.Error("Only issues can be resolved")

    if issue.is_draft:
        raise api.comment.Error("Unpublished issues cannot be resolved")

    transaction.tables.add("commentchanges")

    draft_changes = await issue.draft_changes
    review = await issue.review

    transaction.finalizers.add(UpdateUnpublishedTag(review))
    transaction.finalizers.add(UpdateWouldBeAcceptedTag(review))

    if draft_changes:
        new_state = draft_changes.new_state
        new_type = draft_changes.new_type
        if (new_state and new_state != "open") or new_type:
            raise api.comment.Error("Issue has unpublished conflicting modifications")

        if new_state == "open":
            await transaction.execute(
                Delete("commentchanges").where(
                    author=critic.effective_user, comment=issue
                )
            )
            return

    if issue.state != "open":
        raise api.comment.Error("Only open issues can be resolved")

    await transaction.execute(
        Insert("commentchanges").values(
            comment=issue,
            author=critic.effective_user,
            from_state="open",
            to_state="resolved",
        )
    )
