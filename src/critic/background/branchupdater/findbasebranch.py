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
from typing import Dict, Iterable, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess


async def find_base_branch(
    tip: api.commit.Commit,
    *,
    commits: Iterable[gitaccess.GitCommit] = None,
    exclude_branches: Iterable[api.branch.Branch] = None
) -> Tuple[Optional[api.branch.Branch], api.commitset.CommitSet]:
    """Find the base branch for a newly created branch given its tip

       This performs a depth-first search for any commit reachable from |tip|
       that is associated with an existing branch. When such a commit is found,
       the oldest (lowest branch id) branch with which that commit is associated
       is selected.

       The return value is a tuple of the base branch and an
       api.commitset.CommitSet object consisting of the commits to associate
       with the created branch.

       If no base branch is found, the first item of the returned tuple is None,
       and the second is an api.commitset.CommitSet object consisting of all
       commits reachable from |tip|."""

    critic = tip.critic

    if exclude_branches is not None:
        exclude_branch_ids = [branch.id for branch in exclude_branches]
    else:
        exclude_branch_ids = [-1]

    async def inner(
        tip: api.commit.Commit,
    ) -> Union[Tuple[int, api.commit.Commit], api.commitset.CommitSet]:
        repository_id = tip.repository.id
        stack = [tip]
        processed: Set[api.commit.Commit] = set()
        commits = set()

        commits_by_id: Dict[int, api.commit.Commit] = {}
        batch_size = 20

        async def process_batch() -> Union[
            Tuple[None, None], Tuple[int, api.commit.Commit]
        ]:
            commit_ids = list(commits_by_id.keys())
            async with api.critic.Query[Tuple[int, int]](
                critic,
                """SELECT branchcommits.commit, MIN(branches.id)
                     FROM branchcommits
                     JOIN branches
                            ON (branches.id=branchcommits.branch)
                    WHERE {branchcommits.commit=commit_ids:array}
                      AND branches.repository={repository_id}
                      AND NOT ({branches.id=exclude_branch_ids:array})
                 GROUP BY branchcommits.commit""",
                repository_id=repository_id,
                exclude_branch_ids=exclude_branch_ids,
                commit_ids=commit_ids,
            ) as result:
                base_branch_ids = {
                    commit_id: branch_id async for commit_id, branch_id in result
                }
            if base_branch_ids:
                for commit_id in commit_ids:
                    if commit_id in base_branch_ids:
                        return (base_branch_ids[commit_id], commits_by_id[commit_id])
            commits_by_id.clear()
            return None, None

        while stack:
            commit = stack.pop()

            # Make sure we only process each commit (and its ancestors)
            # once.
            if commit in processed:
                continue
            processed.add(commit)

            commits_by_id[commit.id] = commit

            if len(commits_by_id) == batch_size:
                base_branch_id, tail_commit = await process_batch()
                if base_branch_id is not None and tail_commit is not None:
                    return base_branch_id, tail_commit
                batch_size += batch_size

            commits.add(commit)
            stack.extend(reversed(await commit.parents))

        if commits_by_id:
            base_branch_id, tail_commit = await process_batch()
            if base_branch_id is not None and tail_commit is not None:
                return base_branch_id, tail_commit

        return await api.commitset.create(critic, commits)

    if commits:
        async with api.critic.Query[int](
            critic,
            """SELECT 1
                 FROM branches
                WHERE repository={repository}
                LIMIT 1""",
            repository=tip.repository,
        ) as result:
            is_first_branch = await result.empty()

        if is_first_branch:
            return (
                None,
                await api.commitset.create(
                    critic,
                    await api.commit.fetchMany(tip.repository, low_levels=commits),
                ),
            )

    from ...base.profiling import timed

    with timed("find_inner_branch.inner()"):
        inner_result = await inner(tip)

    base_branch: Optional[api.branch.Branch]

    if isinstance(inner_result, api.commitset.CommitSet):
        return None, inner_result

    base_branch_id, tail = inner_result

    base_branch = await api.branch.fetch(critic, base_branch_id)
    associated_commits = await api.commitset.calculateFromBranchUpdate(
        critic, None, tail, tip
    )

    return base_branch, associated_commits
