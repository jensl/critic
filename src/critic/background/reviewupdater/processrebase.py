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
import textwrap
from typing import Sequence, Tuple

logger = logging.getLogger(__name__)

from critic import api
from critic import background
from critic import dbaccess
from critic.base import asserted

from ..branchupdater.insertcommits import insert_commits
from ..githook import emit_output
from ..replayer import extract_unmerged_paths


class RebaseProcessingResult:
    def __init__(
        self,
        *,
        new_upstream: api.commit.Commit = None,
        changesets: Sequence[api.changeset.Changeset] = (),
        equivalent_merge: api.commit.Commit = None,
        replayed_rebase: api.commit.Commit = None,
    ):
        self.new_upstream = new_upstream
        self.changesets = changesets
        self.equivalent_merge = equivalent_merge
        self.replayed_rebase = replayed_rebase


class RebaseProcessingFailure(Exception):
    def __init__(self, traceback: str):
        self.traceback = traceback


async def process_rebase(
    review: api.review.Review,
    branchupdate: api.branchupdate.BranchUpdate,
    pendingrefupdate_id: int,
) -> RebaseProcessingResult:
    rebase = await review.pending_rebase
    assert rebase

    if isinstance(rebase, api.log.rebase.HistoryRewrite):
        return await process_history_rewrite(
            review, rebase.as_history_rewrite, branchupdate, pendingrefupdate_id
        )
    else:
        return await process_move_rebase(
            review, rebase.as_move_rebase, branchupdate, pendingrefupdate_id
        )


async def process_history_rewrite(
    review: api.review.Review,
    rebase: api.log.rebase.HistoryRewrite,
    branchupdate: api.branchupdate.BranchUpdate,
    pendingrefupdate_id: int,
) -> RebaseProcessingResult:
    await emit_output(review.critic, pendingrefupdate_id, "Performed history rewrite.")
    return RebaseProcessingResult()


async def process_move_rebase(
    review: api.review.Review,
    rebase: api.log.rebase.MoveRebase,
    branchupdate: api.branchupdate.BranchUpdate,
    pendingrefupdate_id: int,
) -> RebaseProcessingResult:
    critic = review.critic
    branch = asserted(await review.branch)
    commits = await branch.commits
    upstreams = await commits.filtered_tails

    old_head = await branchupdate.from_head
    new_head = await branchupdate.to_head

    full_changeset = await api.changeset.fetch(
        critic, from_commit=old_head, to_commit=new_head
    )

    new_upstream = await rebase.new_upstream
    if new_upstream:
        assert upstreams == {new_upstream}
    else:
        (new_upstream,) = upstreams

    old_upstream = await rebase.old_upstream

    if await old_upstream.isAncestorOf(new_upstream):
        handler = process_ff_move_rebase
    else:
        handler = process_non_ff_move_rebase

    result = await handler(
        review, rebase, branchupdate, new_upstream, pendingrefupdate_id
    )

    await full_changeset.ensure("changedlines")

    return result


async def process_ff_move_rebase(
    review: api.review.Review,
    rebase: api.log.rebase.MoveRebase,
    branchupdate: api.branchupdate.BranchUpdate,
    new_upstream: api.commit.Commit,
    pendingrefupdate_id: int,
) -> RebaseProcessingResult:
    critic = review.critic
    repository = await review.repository
    branch = asserted(await review.branch)
    old_upstream = asserted(await rebase.old_upstream)
    old_head = asserted(await branchupdate.from_head)
    new_head = await branchupdate.to_head

    await emit_output(
        critic,
        pendingrefupdate_id,
        "Generating and replaying equivalent merge commit ...",
    )

    class InsertRequest(Exception):
        pass

    message = f"Merge {new_upstream.sha1} into {branch.name}\n\n" + textwrap.fill(
        "This commit was generated automatically by Critic as an "
        '"equivalent merge" to the rebase of the commits '
        f"{old_upstream.sha1[:8]}..{old_head.sha1[:8]} onto the "
        f"commit {new_upstream.sha1[:8]}, for the purpose of "
        "visualizing conflict resolutions and other changes "
        "introduced as part of the rebase."
    )

    repository.low_level.set_user_details("Critic System", api.critic.getSystemEmail())
    merge_sha1 = await repository.low_level.committree(
        new_head.tree, [old_head.sha1, new_upstream.sha1], message
    )
    repository.low_level.clear_user_details()

    await insert_commits(repository, merge_sha1)

    merge = await api.commit.fetch(repository, sha1=merge_sha1)
    # replay = await replay_merge(repository, merge)

    async def fetch_replay_id() -> Tuple[int, str]:
        async with api.critic.Query[Tuple[int, str]](
            critic,
            """SELECT replay, traceback
                 FROM mergereplayrequests
                WHERE repository={repository}
                  AND merge={merge}""",
            repository=repository,
            merge=merge,
        ) as result:
            try:
                return await result.one()
            except dbaccess.ZeroRowsInResult:
                raise InsertRequest from None

    iterations = 1

    while True:
        try:
            replay_id, traceback = await fetch_replay_id()
        except InsertRequest:
            async with critic.transaction() as cursor:
                await cursor.execute(
                    """INSERT
                         INTO mergereplayrequests (repository, merge)
                       VALUES ({repository}, {merge})""",
                    repository=repository,
                    merge=merge,
                )

            logger.debug("requested merge replay")

            background.utils.wakeup_direct("replayer")
        else:
            if replay_id is not None or traceback is not None:
                break

        logger.debug("sleeping %d seconds, waiting for replay", min(60, iterations))

        await asyncio.sleep(min(60, iterations))
        iterations += 1

    if traceback is not None:
        await emit_output(review.critic, pendingrefupdate_id, "  failed!")
        raise RebaseProcessingFailure(traceback)

    replay = await api.commit.fetch(repository, replay_id)
    unmerged_paths = extract_unmerged_paths(replay)

    await emit_output(review.critic, pendingrefupdate_id, "  done.")

    changeset = await api.changeset.fetch(
        critic, from_commit=new_head, to_commit=replay, conflicts=True
    )

    await changeset.ensure("changedlines")

    # FIXME: Should add more than one changeset here!
    changesets = (changeset,)

    if unmerged_paths:
        output = "Conflicts detected in the following paths:\n  "
        output += "\n  ".join(unmerged_paths)
    elif len(await changeset.files) == 0:
        output = "No overlapping changes detected."
        changesets = ()
    else:
        output = "Overlapping changes detected."

    await emit_output(review.critic, pendingrefupdate_id, output)

    return RebaseProcessingResult(
        new_upstream=new_upstream, changesets=changesets, equivalent_merge=merge
    )


async def process_non_ff_move_rebase(
    review: api.review.Review,
    rebase: api.log.rebase.MoveRebase,
    branchupdate: api.branchupdate.BranchUpdate,
    new_upstream: api.commit.Commit,
    pendingrefupdate_id: int,
) -> RebaseProcessingResult:
    critic = review.critic
    repository = await review.repository
    new_head = await branchupdate.to_head

    await emit_output(review.critic, pendingrefupdate_id, "Replaying rebase ...")

    class InsertRequest(Exception):
        pass

    async def fetch_replay_id() -> Tuple[int, str]:
        async with api.critic.Query[Tuple[int, str]](
            critic,
            """SELECT replay, traceback
                 FROM rebasereplayrequests
                WHERE rebase={rebase}
                  AND branchupdate={branchupdate}
                  AND new_upstream={new_upstream}""",
            rebase=rebase,
            branchupdate=branchupdate,
            new_upstream=new_upstream,
        ) as result:
            try:
                return await result.one()
            except dbaccess.ZeroRowsInResult:
                raise InsertRequest from None

    iterations = 1

    while True:
        try:
            replay_id, traceback = await fetch_replay_id()
        except InsertRequest:
            async with critic.transaction() as cursor:
                await cursor.execute(
                    """INSERT
                         INTO rebasereplayrequests (rebase, branchupdate,
                                                    new_upstream)
                       VALUES ({rebase}, {branchupdate}, {new_upstream})""",
                    rebase=rebase,
                    branchupdate=branchupdate,
                    new_upstream=new_upstream,
                )

            logger.debug("requested rebase replay")

            background.utils.wakeup_direct("replayer")
        else:
            if replay_id is not None or traceback is not None:
                break

        logger.debug("sleeping %d seconds, waiting for replay", min(60, iterations))

        await asyncio.sleep(min(60, iterations))
        iterations += 1

    if traceback is not None:
        await emit_output(review.critic, pendingrefupdate_id, "  failed!")
        raise RebaseProcessingFailure(traceback)

    replay = await api.commit.fetch(repository, replay_id)
    unmerged_paths = extract_unmerged_paths(replay)

    await emit_output(review.critic, pendingrefupdate_id, "  done.")

    changeset = await api.changeset.fetch(
        critic, from_commit=new_head, to_commit=replay, conflicts=True
    )

    await changeset.ensure("changedlines")

    changesets = (changeset,)

    if unmerged_paths:
        output = "Conflicts detected in the following paths:\n  "
        output += "\n  ".join(unmerged_paths)
    elif len(await changeset.files) == 0:
        output = "No overlapping changes detected."
        changesets = ()
    else:
        output = "Overlapping changes (e.g. conflict resolutions) detected."

    await emit_output(review.critic, pendingrefupdate_id, output)

    return RebaseProcessingResult(
        new_upstream=new_upstream, changesets=changesets, replayed_rebase=replay
    )
