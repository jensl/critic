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

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

from . import list_unmerged_paths
from ..branchupdater.insertcommits import insert_commits
from critic import api
from critic import base
from critic import gitaccess


async def replay_rebase(
    rebase: api.log.rebase.MoveRebase,
    branchupdate: api.branchupdate.BranchUpdate,
    new_upstream: api.commit.Commit,
) -> api.commit.Commit:
    review = await rebase.review
    repository = await review.repository
    branch = await review.branch
    old_upstream = await rebase.old_upstream
    old_head = await branchupdate.from_head

    assert branch
    assert old_head

    worktrees_dir = os.path.join(base.configuration()["paths.home"], "worktrees")

    if not os.path.isdir(worktrees_dir):
        os.mkdir(worktrees_dir, 0o700)

    low_level = gitaccess.GitRepository.direct(repository.path)
    low_level.set_user_details("Critic System", api.critic.getSystemEmail())

    message = f"replay of rebase of {branch.name} onto {new_upstream.sha1}"

    output = await low_level.run(
        "commit-tree", old_head.tree, "-p", old_upstream.sha1, stdin_data=message
    )
    squash_sha1 = output.decode().strip()

    with tempfile.TemporaryDirectory(dir=worktrees_dir) as worktree_dir:
        await low_level.run(
            "worktree", "add", "--detach", worktree_dir, new_upstream.sha1
        )

        low_level.set_worktree_path(worktree_dir)

        try:
            await low_level.run("cherry-pick", "--allow-empty", squash_sha1)
        except gitaccess.GitProcessError:
            message += "\n\nunmerged paths:\n" + "\n".join(
                await list_unmerged_paths(low_level)
            )

            # Merge conflicts is fine; we aim to visualize them, so just go
            # ahead and commit anyway.
            await low_level.run("commit", "-a", "-m", message)

        replay_sha1 = await low_level.revparse("HEAD", object_type="commit")

        logger.debug(
            "created replay %s for rebase of %s onto %s",
            replay_sha1,
            branch.name,
            new_upstream.sha1,
        )

        await low_level.updateref(
            "refs/keepalive/" + replay_sha1, new_value=replay_sha1
        )

    low_level.set_worktree_path(None)

    await low_level.run("worktree", "prune")
    await insert_commits(repository, replay_sha1)

    return await api.commit.fetch(repository, sha1=replay_sha1)
