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

import asyncio
import logging

logger = logging.getLogger(__name__)

from critic import api
from critic import pubsub


async def process_initial_commits(review: api.review.Review) -> None:
    critic = review.critic
    initial_commits = await review.commits

    # Request that changesets be processed for each individual commit in the
    # set.
    changesets = []

    for commit in initial_commits.topo_ordered:
        changesets.append(await api.changeset.fetch(critic, single_commit=commit))

    if len(initial_commits) > 1:
        # Also request that a changeset of the full changes is processed right
        # away, since this is likely to be wanted by reviewers.
        try:
            await api.changeset.fetchAutomatic(review, "everything")
        except api.changeset.Error:
            # This is sometimes not supported, e.g. if the first (oldest) commit
            # on the review branch is a merge. Nothing to worry about.
            pass

    # Ensure (i.e. wait for) processing of changed lines. We need to know the
    # number of deleted/inserted lines when inserting rows into `reviewfiles`
    # and assign changes to reviewers.
    for changeset in changesets:
        logger.debug("Waiting for changeset.ensure('changedlines'): %d", changeset.id)
        await changeset.ensure("changedlines")

    logger.debug(
        "Adding changesets to review r/%d: %s",
        review.id,
        ", ".join(str(changeset.id) for changeset in changesets),
    )
    async with api.transaction.start(critic) as transaction:
        modifier = transaction.modifyReview(review)
        await modifier.addChangesets(changesets, commits=initial_commits)
        api.transaction.review.CreatedReviewEvent.ensure(transaction, review, "ready")
