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
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api


async def ensure_changesets(
    review: api.review.Review, commits: Optional[api.commitset.CommitSet] = None
) -> Sequence[api.changeset.Changeset]:
    """Request and wait for necessary changesets when adding commits to review

    This is used both when creating a review and when adding additional
    commits to it.

    If |commits| is None, |review.commits| is used."""

    critic = review.critic

    if commits is None:
        use_commits = await review.commits
    else:
        use_commits = commits

    assert isinstance(use_commits, api.commitset.CommitSet)

    # Request that changesets be processed for each individual commit in the
    # set.
    changesets = []
    for commit in use_commits:
        changesets.append(await api.changeset.fetch(critic, single_commit=commit))

    if commits is not None or len(use_commits) > 1:
        # Also request that a changeset of the full changes is processed right
        # away, since this is likely to be wanted by reviewers. We will not
        # wait for this to finish, however, since it is not needed to update
        # the review state. (And may in fact end up never used by anyone.)
        try:
            await api.changeset.fetchAutomatic(review, "everything")
        except api.changeset.Error:
            # This is sometimes not supported, e.g. if the first (oldest) commit
            # on the review branch is a merge. Nothing to worry about.
            pass

    # Ensure (i.e. wait for) processing of changed lines. We need to know the
    # number of deleted/inserted lines when inserting rows into `reviewfiles`
    # and assign changes to reviewers.
    logger.debug(
        "Waiting for changeset.ensure('changedlines'): %s",
        ", ".join(str(changeset.id) for changeset in changesets),
    )
    await critic.gather(*(changeset.ensure("changedlines") for changeset in changesets))

    return changesets
