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
from typing import (
    Any,
    Collection,
    Iterable,
    Optional,
    Sequence,
)

logger = logging.getLogger(__name__)

from critic import api
from critic import gitaccess
from critic import textutils
from critic.api.reviewintegrationrequest import ReviewIntegrationRequest
from critic.api.transaction.reviewintegrationrequest import StepsTaken
from critic.base import asserted
from critic.gitaccess import SHA1

from ..branchupdater.insertcommits import insert_commits
from ..branchupdater.updatebranch import update_branch


class IntegrationRejected(Exception):
    def __init__(
        self,
        message: str,
        *,
        propagate: bool = False,
        steps_taken: Optional[StepsTaken] = None,
    ):
        self.message = message
        self.propagate = propagate
        self.steps_taken = steps_taken or StepsTaken()


async def perform_rebase(
    request: ReviewIntegrationRequest,
    review: api.review.Review,
    new_head: api.commit.Commit,
    *,
    new_upstream: Optional[api.commit.Commit] = None,
    squashed: bool = False,
    autosquashed: bool = False,
    strategy_used: Optional[api.review.IntegrationStrategy] = None,
) -> api.commitset.CommitSet:
    critic = review.critic
    repository = await review.repository
    branch = asserted(await review.branch)
    old_head = await branch.head
    old_commits = await branch.commits
    old_upstream = await old_commits.upstream
    new_commits = await api.commitset.calculateFromRange(
        critic, old_upstream if new_upstream is None else new_upstream, new_head
    )
    associated_commits = new_commits - old_commits
    disassociated_commits = old_commits - new_commits
    async with api.transaction.start(critic) as transaction:
        branch_modifier = await transaction.modifyRepository(repository).modifyBranch(
            branch
        )
        branchupdate = await (
            branch_modifier.recordUpdate(
                new_head,
                await branch.base_branch,
                associated_commits,
                disassociated_commits,
            )
        )

        review_modifier = transaction.modifyReview(review)

        await review_modifier.recordRebase(
            branchupdate,
            old_upstream=None if new_upstream is None else old_upstream,
            new_upstream=new_upstream,
        )

        request_modifier = await review_modifier.modifyIntegrationRequest(request)

        await request_modifier.recordBranchUpdate(
            branchupdate, StepsTaken(strategy_used, squashed, autosquashed)
        )

        async def update_ref() -> None:
            await repository.low_level.updateref(
                f"refs/heads/{branch.name}",
                old_value=old_head.sha1,
                new_value=new_head.sha1,
            )

        transaction.post_commit_callbacks.append(update_ref)

    return new_commits


async def worktree_run(
    worktree: gitaccess.GitRepository, *args: str, **rejection_kwargs: Any
) -> SHA1:
    def process_args(args: Sequence[str]) -> Iterable[str]:
        for arg in args:
            yield '"..."' if " " in arg or "\n" in arg else arg

    def process_output(output: Optional[bytes]) -> str:
        return textutils.filtercr(textutils.decode(output or "")).strip()

    try:
        await worktree.run(*args)
    except gitaccess.GitProcessError as error:
        status_output = await worktree.run("status")
        diff_output = await worktree.run("diff")
        error_message = f"""\
=== git {" ".join(process_args(args))} ===
{process_output(error.stderr) or process_output(error.stdout)}


=== git status ===
{process_output(status_output)}


=== git diff ===
{process_output(diff_output)}"""
        raise IntegrationRejected(error_message, **rejection_kwargs) from None
    return await worktree.revparse("HEAD", object_type="commit")


async def squash(
    review: api.review.Review, request: ReviewIntegrationRequest, message: str
) -> None:
    repository = await review.repository
    branch = await review.branch
    assert branch
    old_head = await branch.head
    old_commits = await branch.commits
    try:
        (upstream,) = await old_commits.filtered_tails
    except ValueError:
        raise Exception("irregular branch")
    with repository.withSystemUserDetails(author=False) as gitrepository:
        gitrepository.set_author_details(old_head.author.name, old_head.author.email)
        sha1 = await gitrepository.committree(old_head.tree, [upstream.sha1], message)
    await insert_commits(repository, sha1)
    new_head = await api.commit.fetch(repository, sha1=sha1)
    await perform_rebase(request, review, new_head, squashed=True)


async def autosquash(
    review: api.review.Review, request: ReviewIntegrationRequest
) -> None:
    repository = await review.repository
    branch = await review.branch
    assert branch
    old_head = await branch.head
    old_commits = await branch.commits
    # Check if there are any fixup! or squash! commits on the branch.
    summaries = set()
    for commit in old_commits:
        summary, _, _ = commit.message.partition("\n")
        summaries.add(summary)
        summaries.add(commit.sha1)
    for commit in old_commits:
        summary, _, _ = commit.message.partition("\n")
        if summary.startswith("fixup! "):
            reference = summary[len("fixup! ") :].strip()
        elif summary.startswith("squash! "):
            reference = summary[len("squash! ") :].strip()
        else:
            continue
        if reference in summaries:
            break
    else:
        logger.debug("no fixup!/squash! commits identified")
        return
    try:
        (upstream,) = await old_commits.filtered_tails
    except ValueError:
        raise Exception("irregular branch")
    with repository.withSystemUserDetails(author=False) as gitrepository:
        async with gitrepository.worktree(old_head) as worktree:
            with worktree.with_environ(GIT_SEQUENCE_EDITOR="true"):
                sha1 = await worktree_run(
                    worktree,
                    "rebase",
                    "-i",
                    "--autosquash",
                    str(upstream),
                    autosquashed=True,
                )
    await insert_commits(repository, sha1)
    new_head = await api.commit.fetch(repository, sha1=sha1)
    await perform_rebase(request, review, new_head, autosquashed=True)


async def fast_forward(
    review: api.review.Review, request: ReviewIntegrationRequest, unconditional: bool
) -> bool:
    repository = await review.repository
    target_branch = await request.target_branch
    target_head = await target_branch.head
    review_branch = await review.branch
    assert review_branch
    review_head = await review_branch.head

    if not await target_head.isAncestorOf(review_head):
        if unconditional:
            raise IntegrationRejected(
                "must be fast-forward", steps_taken=StepsTaken("fast-forward")
            )
        return False

    async with api.transaction.start(review.critic) as transaction:
        branch_modifier = await transaction.modifyRepository(repository).modifyBranch(
            target_branch
        )
        branchupdate = await branch_modifier.recordUpdate(
            review_head,
            await target_branch.base_branch,
            await review_branch.commits,
            api.commitset.empty(review.critic),
            previous_head=target_head,
        )

        request_modifier = await transaction.modifyReview(
            review
        ).modifyIntegrationRequest(request)

        await request_modifier.recordBranchUpdate(
            branchupdate, StepsTaken("fast-forward")
        )

        async def update_target_branch() -> None:
            await repository.low_level.updateref(
                target_branch.ref,
                old_value=target_head.sha1,
                new_value=review_head.sha1,
            )

        transaction.post_commit_callbacks.append(update_target_branch)

    return True


async def cherry_pick(
    review: api.review.Review, request: ReviewIntegrationRequest, unconditional: bool
) -> bool:
    repository = await review.repository
    target_branch = await request.target_branch
    target_head = await target_branch.head
    review_branch = asserted(await review.branch)
    review_head = await review_branch.head

    if review_branch.size != 1:
        if unconditional:
            raise IntegrationRejected(
                "review branch must contain a single commit",
                steps_taken=StepsTaken("cherry-pick"),
            )
        return False

    if review_head.is_merge:
        if unconditional:
            raise IntegrationRejected(
                "will not cherry-pick a merge commit",
                steps_taken=StepsTaken("cherry-pick"),
            )
        return False

    if not await target_head.isAncestorOf(review_head):
        with repository.withSystemUserDetails(author=False) as gitrepository:
            async with gitrepository.worktree(target_head) as worktree:
                sha1 = await worktree_run(
                    worktree,
                    "cherry-pick",
                    str(review_head),
                    strategy_used="cherry-pick",
                )
        await insert_commits(repository, sha1)
        review_head = await api.commit.fetch(repository, sha1=sha1)
        await perform_rebase(request, review, review_head, new_upstream=target_head)

    async with api.transaction.start(review.critic) as transaction:
        branch_modifier = await transaction.modifyRepository(repository).modifyBranch(
            target_branch
        )
        branchupdate = await branch_modifier.recordUpdate(
            review_head,
            await target_branch.base_branch,
            await api.commitset.create(review.critic, [review_head]),
            api.commitset.empty(review.critic),
            previous_head=target_head,
        )

        request_modifier = await transaction.modifyReview(
            review
        ).modifyIntegrationRequest(request)

        await request_modifier.recordBranchUpdate(
            branchupdate, StepsTaken("cherry-pick")
        )

        async def update_target_branch() -> None:
            await repository.low_level.updateref(
                target_branch.ref,
                old_value=target_head.sha1,
                new_value=review_head.sha1,
            )

        transaction.post_commit_callbacks.append(update_target_branch)

    return True


async def rebase(review: api.review.Review, request: ReviewIntegrationRequest) -> None:
    repository = await review.repository
    target_branch = await request.target_branch
    target_head = await target_branch.head
    review_branch = asserted(await review.branch)
    review_head = await review_branch.head

    if not await target_head.isAncestorOf(review_head):
        with repository.withSystemUserDetails(author=False) as gitrepository:
            flags: Collection[gitaccess.RevlistFlag] = (  # type: ignore
                "right-only",
                "cherry-pick",
                "no-merges",
                "reverse",
            )
            async with gitrepository.worktree(target_head) as worktree:
                pick_sha1s = await gitrepository.revlist(
                    symmetric=(target_head.sha1, review_head.sha1), flags=flags
                )
                if not pick_sha1s:
                    raise IntegrationRejected(
                        "no commits to cherry-pick onto target branch",
                        steps_taken=StepsTaken("rebase"),
                    )
                for pick_sha1 in pick_sha1s[:-1]:
                    await worktree_run(
                        worktree,
                        "cherry-pick",
                        pick_sha1,
                        steps_taken=StepsTaken("rebase"),
                    )
                sha1 = await worktree_run(
                    worktree,
                    "cherry-pick",
                    pick_sha1s[-1],
                    steps_taken=StepsTaken("rebase"),
                )
        await insert_commits(repository, sha1)
        review_head = await api.commit.fetch(repository, sha1=sha1)
        associated_commits = await perform_rebase(
            request, review, review_head, new_upstream=target_head
        )
    else:
        associated_commits = await api.commitset.calculateFromRange(
            review.critic, target_head, review_head
        )

    async with api.transaction.start(review.critic) as transaction:
        branch_modifier = await transaction.modifyRepository(repository).modifyBranch(
            target_branch
        )
        branchupdate = await branch_modifier.recordUpdate(
            review_head,
            await target_branch.base_branch,
            associated_commits,
            api.commitset.empty(review.critic),
            previous_head=target_head,
        )

        request_modifier = await transaction.modifyReview(
            review
        ).modifyIntegrationRequest(request)

        await request_modifier.recordBranchUpdate(branchupdate, StepsTaken("rebase"))

        async def update_target_branch() -> None:
            await repository.low_level.updateref(
                target_branch.ref,
                old_value=target_head.sha1,
                new_value=review_head.sha1,
            )

        transaction.post_commit_callbacks.append(update_target_branch)


async def merge(review: api.review.Review, request: ReviewIntegrationRequest) -> None:
    repository = await review.repository
    target_branch = await request.target_branch
    target_head = await target_branch.head
    review_branch = await review.branch
    assert review_branch
    review_head = await review_branch.head

    with repository.withSystemUserDetails(author=False) as gitrepository:
        async with gitrepository.worktree(target_head) as worktree:
            message = f"Merge branch '{review_branch.name}' into {target_branch.name}"
            sha1 = await worktree_run(
                worktree,
                "merge",
                "--no-ff",
                "-m",
                message,
                str(review_head),
                strategy_used="merge",
            )
    await insert_commits(repository, sha1)

    branchupdate = await update_branch(
        target_branch,
        target_head,
        await api.commit.fetch(repository, sha1=sha1),
        output=["Integrating r/{review.id}: {review.summary}"],
        perform_update=True,
        force_associate=await review_branch.commits,
    )

    async with api.transaction.start(review.critic) as transaction:
        request_modifier = await transaction.modifyReview(
            review
        ).modifyIntegrationRequest(request)

        await request_modifier.recordBranchUpdate(branchupdate, StepsTaken("merge"))


async def process_integration_request(
    review: api.review.Review, request_id: int
) -> None:
    critic = review.critic

    request = await api.reviewintegrationrequest.fetch(critic, request_id)

    async def inner() -> None:
        squashed: Optional[bool] = None
        autosquashed: Optional[bool] = None
        strategy_used: Optional[api.review.IntegrationStrategy] = None

        try:
            if request.squash_requested:
                squashed = True
                assert request.squash_message is not None
                await squash(review, request, request.squash_message)
            elif request.autosquash_requested:
                autosquashed = True
                await autosquash(review, request)

            if request.integration_requested:
                if not await review.is_accepted:
                    raise IntegrationRejected("review is not accepted")

                try:
                    integration_setting = await api.branchsetting.fetch(
                        critic,
                        branch=await request.target_branch,
                        scope="integration",
                        name="strategy",
                    )
                except api.branchsetting.NotDefined:
                    raise IntegrationRejected(
                        "integration not configured for target branch"
                    )
                else:
                    strategy = integration_setting.value

                logger.debug("integration strategy: %r", strategy)

                if "fast-forward" in strategy:
                    strategy_used = "fast-forward"
                    if await fast_forward(
                        review, request, strategy == ["fast-forward"]
                    ):
                        return

                if "cherry-pick" in strategy:
                    strategy_used = "cherry-pick"
                    if await cherry_pick(review, request, strategy == ["cherry-pick"]):
                        return

                if "rebase" in strategy:
                    strategy_used = "rebase"
                    await rebase(review, request)
                elif "merge" in strategy:
                    strategy_used = "merge"
                    await merge(review, request)
                else:
                    raise IntegrationRejected("no configured strategy supported")
        except IntegrationRejected:
            raise
        except Exception:
            raise IntegrationRejected(
                "an unexpected error occurred",
                propagate=True,
                steps_taken=StepsTaken(strategy_used, squashed, autosquashed),
            )

    try:
        await inner()
    except IntegrationRejected as rejection:
        async with api.transaction.start(critic) as transaction:
            request_modifier = await transaction.modifyReview(
                review
            ).modifyIntegrationRequest(request)

            await request_modifier.recordFailure(
                rejection.steps_taken, rejection.message
            )
        if rejection.propagate:
            raise
    else:
        async with api.transaction.start(critic) as transaction:
            request_modifier = await transaction.modifyReview(
                review
            ).modifyIntegrationRequest(request)

            await request_modifier.recordSuccess()
