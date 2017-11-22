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
from typing import Any, Dict, Iterable, Optional, Sequence, Union

logger = logging.getLogger(__name__)

from critic import api
from critic import dbaccess
from critic import gitaccess
from critic import textutils
from critic.api.reviewintegrationrequest import ReviewIntegrationRequest
from critic.base import asserted
from critic.gitaccess import SHA1

from ..branchupdater.insertcommits import insert_commits
from ..branchupdater.updatebranch import update_branch


class IntegrationRejected(Exception):
    def __init__(self, message: str, *, propagate: bool = False, **kwargs: Any):
        self.message = message
        self.propagate = propagate
        self.kwargs = kwargs


def update_request(
    transaction: api.transaction.Transaction,
    request: ReviewIntegrationRequest,
    **kwargs: Any,
) -> None:
    transaction.items.append(
        api.transaction.Update("reviewintegrationrequests")
        .set(**kwargs)
        .where(id=request)
    )


async def perform_rebase(
    request: ReviewIntegrationRequest,
    review: api.review.Review,
    new_head: api.commit.Commit,
    *,
    new_upstream: api.commit.Commit = None,
    **kwargs: dbaccess.Parameter,
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
        transaction.modifyReview(review).recordRebase(
            branchupdate,
            old_upstream=None if new_upstream is None else old_upstream,
            new_upstream=new_upstream,
        )
        update_request(transaction, request, branchupdate=branchupdate, **kwargs)

        async def update_ref() -> None:
            repository.low_level.updateref(
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
        return textutils.filtercr(textutils.decode(output)).strip()

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
    gitrepository = repository.low_level
    gitrepository.set_author_details(old_head.author.name, old_head.author.email)
    gitrepository.set_committer_details("Critic System", api.critic.getSystemEmail())
    sha1 = await gitrepository.committree(old_head.tree, [upstream.sha1], message)
    gitrepository.clear_user_details()
    await insert_commits(repository, sha1)
    new_head = await api.commit.fetch(repository, sha1=sha1)
    await perform_rebase(request, review, new_head, squashed=True)


async def autosquash(
    review: api.review.Review, request: ReviewIntegrationRequest
) -> bool:
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
        return False
    try:
        (upstream,) = await old_commits.filtered_tails
    except ValueError:
        raise Exception("irregular branch")
    gitrepository = repository.low_level
    gitrepository.set_committer_details("Critic System", api.critic.getSystemEmail())
    async with gitrepository.worktree(old_head) as worktree:
        worktree.environ["GIT_SEQUENCE_EDITOR"] = "true"
        sha1 = await worktree_run(
            worktree, "rebase", "-i", "--autosquash", str(upstream), autosquashed=True
        )
    await insert_commits(repository, sha1)
    new_head = await api.commit.fetch(repository, sha1=sha1)
    await perform_rebase(request, review, new_head, autosquashed=True)
    return True


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
                "must be fast-forward", strategy_used="fast-forward"
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

        update_request(
            transaction,
            request,
            branchupdate=branchupdate,
            strategy_used="fast-forward",
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
                strategy_used="cherry-pick",
            )
        return False

    if review_head.is_merge:
        if unconditional:
            raise IntegrationRejected(
                "will not cherry-pick a merge commit", strategy_used="cherry-pick"
            )
        return False

    if not await target_head.isAncestorOf(review_head):
        gitrepository = repository.low_level
        gitrepository.set_committer_details(
            "Critic System", api.critic.getSystemEmail()
        )
        async with gitrepository.worktree(target_head) as worktree:
            sha1 = await worktree_run(
                worktree, "cherry-pick", str(review_head), strategy_used="cherry-pick"
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

        update_request(
            transaction, request, branchupdate=branchupdate, strategy_used="cherry-pick"
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
        gitrepository = repository.low_level
        gitrepository.set_committer_details(
            "Critic System", api.critic.getSystemEmail()
        )
        async with gitrepository.worktree(target_head) as worktree:
            pick_sha1s = await gitrepository.revlist(
                symmetric=(target_head.sha1, review_head.sha1),
                flags={"right-only", "cherry-pick", "no-merges", "reverse"},
            )
            if not pick_sha1s:
                raise IntegrationRejected(
                    "no commits to cherry-pick onto target branch",
                    strategy_used="rebase",
                )
            for pick_sha1 in pick_sha1s:
                sha1 = await worktree_run(
                    worktree, "cherry-pick", pick_sha1, strategy_used="rebase"
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

        update_request(
            transaction, request, branchupdate=branchupdate, strategy_used="rebase"
        )

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

    gitrepository = repository.low_level
    gitrepository.set_user_details("Critic System", api.critic.getSystemEmail())
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
        update_request(
            transaction, request, branchupdate=branchupdate, strategy_used="merge"
        )


async def process_integration_request(
    review: api.review.Review, request_id: int
) -> None:
    critic = review.critic

    request = await api.reviewintegrationrequest.fetch(critic, request_id)

    async def inner() -> bool:
        error_kwargs: Dict[str, Union[bool, str]] = {}
        try:
            if request.squash_requested:
                error_kwargs = {"squashed": True}
                await squash(review, request, request.squash_message)
            elif request.autosquash_requested:
                error_kwargs = {"autosquashed": True}
                if not await autosquash(review, request):
                    return False

            if request.integration_requested:
                if not await review.isAccepted:
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
                    error_kwargs = {"strategy_used": "fast-forward"}
                    if await fast_forward(
                        review, request, strategy == ["fast-forward"]
                    ):
                        return True

                if "cherry-pick" in strategy:
                    error_kwargs = {"strategy_used": "cherry-picked"}
                    if await cherry_pick(review, request, strategy == ["cherry-pick"]):
                        return True

                if "rebase" in strategy:
                    error_kwargs = {"strategy_used": "rebase"}
                    await rebase(review, request)
                elif "merge" in strategy:
                    error_kwargs = {"strategy_used": "merge"}
                    await merge(review, request)
                else:
                    raise IntegrationRejected("no configured strategy supported")
        except IntegrationRejected:
            raise
        except Exception:
            raise IntegrationRejected(
                "an unexpected error occurred", propagate=True, **error_kwargs
            )

        return True

    try:
        successful = await inner()
    except IntegrationRejected as rejection:
        async with api.transaction.start(critic) as transaction:
            update_request(
                transaction,
                request,
                successful=False,
                error_message=rejection.message,
                **rejection.kwargs,
            )
        if rejection.propagate:
            raise
    else:
        async with api.transaction.start(critic) as transaction:
            update_request(transaction, request, successful=successful)
