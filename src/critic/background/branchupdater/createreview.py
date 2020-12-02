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
from typing import Optional

logger = logging.getLogger(__name__)

from .autopublish import should_auto_publish
from .createbranch import create_branch
from critic import api
from ...background.githook import reflow, emit_output


async def create_review(
    critic: api.critic.Critic,
    branch_name: str,
    head: api.commit.Commit,
    *,
    pendingrefupdate_id: Optional[int] = None
) -> api.review.Review:
    if critic.effective_user.type == "regular":
        owners = [critic.effective_user]
    else:
        owners = []

    async with api.transaction.start(critic) as transaction:
        logger.debug("creating branch ...")
        created_branch = await create_branch(
            critic,
            branch_name,
            head,
            transaction=transaction,
            pendingrefupdate_id=pendingrefupdate_id,
            is_creating_review=True,
        )

        logger.debug("creating review ...")
        review = (
            await transaction.createReview(
                head.repository, owners, head=head, branch=created_branch, via_push=True
            )
        ).subject

    logger.debug("transaction committed")
    logger.debug("got review")

    lines = ["Review created:"]

    for url_prefix in await critic.effective_user.url_prefixes:
        lines.append("  %s/r/%d" % (url_prefix, review.id))

    lines.append("")

    if await should_auto_publish(review, pendingrefupdate_id=pendingrefupdate_id):
        lines.append("Note: this review will be published automatically.")
    else:
        lines.extend(
            reflow(
                "Note: The review is not published yet, meaning no other users "
                "have been notified about it or will see it. To publish the "
                "review, go to the URL above.",
                hanging_indent=len("Note: "),
            ).splitlines()
        )

    await emit_output(critic, pendingrefupdate_id, "\n".join(lines))

    return review
