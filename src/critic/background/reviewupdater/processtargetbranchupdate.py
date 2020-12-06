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
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic.base import asserted
from critic.gitaccess import GitError

from ..replayer import list_unmerged_paths


async def process_target_branch_update(
    review: api.review.Review,
    branchupdate: api.branchupdate.BranchUpdate,
    callback: Callable[
        [dbaccess.TransactionCursor, Mapping[str, Any]], Awaitable[None]
    ],
) -> None:
    critic = review.critic
    repository = await review.repository
    integration = asserted(await review.integration)
    review_branch = asserted(await review.branch)
    review_branch_head = await review_branch.head
    target_branch = integration.target_branch
    target_branch_head = await target_branch.head

    updates: Dict[str, Any] = {}

    with repository.withSystemUserDetails() as gitrepository:
        new_behind = await gitrepository.revlist(
            include=[target_branch_head.sha1],
            exclude=[review_branch_head.sha1],
            count=True,
        )
        if new_behind != integration.commits_behind:
            updates["integration"] = {"commits_behind": new_behind}

        async with gitrepository.worktree(target_branch_head.sha1, detach=True):
            try:
                await gitrepository.run("merge", review_branch_head.sha1)
            except GitError:
                unmerged_paths = await list_unmerged_paths(gitrepository)
            else:
                unmerged_paths = []

    unmerged_files: Optional[Sequence[api.file.File]]
    if unmerged_paths:
        unmerged_files = await api.file.fetchMany(critic, paths=unmerged_paths)
        if not updates:
            updates = {"integration": {}}
        updates["integration"]["conflicts"] = sorted(file.id for file in unmerged_files)
    else:
        unmerged_files = None

    async with critic.transaction() as cursor:
        await cursor.execute(
            """UPDATE reviews
                  SET integration_branchupdate={branchupdate},
                      integration_behind={behind}
                WHERE id={review}""",
            review=review,
            branchupdate=branchupdate,
            behind=new_behind,
        )

        if unmerged_files:
            await cursor.execute(
                """DELETE
                     FROM reviewintegrationconflicts
                    WHERE review={review}""",
                review=review,
            )
            await cursor.executemany(
                """INSERT
                     INTO reviewintegrationconflicts (review, file)
                   VALUES ({review}, {file})""",
                (
                    dbaccess.parameters(review=review, file=file)
                    for file in unmerged_files
                ),
            )

        if updates:
            await callback(cursor, updates)
