import asyncio
import logging
import pytest
from typing import Collection

logger = logging.getLogger(__name__)

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures.review import CreateReview
from ..fixtures.branch import CreateBranch
from ..fixtures import Snapshot
from ..utilities import Anonymizer, generate_name, map_to_id, raise_for_status


async def create_filter(api: API, repository: CriticRepository, user: User) -> None:
    async with api.session(user) as session:
        await session.create(
            user.name,
            "repositoryfilters",
            {
                "path": "/",
                "repository": repository.id,
                "type": "reviewer",
            },
            RepositoryId="$.request.payload.repository",
        )


@pytest.mark.asyncio
async def test_reviewtags(
    websocket: WebSocket,
    api: API,
    critic_repo: CriticRepository,
    alice: User,
    bob: User,
    carol: User,
    dave: User,
    snapshot: Snapshot,
    anonymizer: Anonymizer,
    create_branch: CreateBranch,
    create_review: CreateReview,
) -> None:
    await create_filter(api, critic_repo, bob)
    await create_filter(api, critic_repo, carol)
    await create_filter(api, critic_repo, dave)

    async def check_tags(label: str) -> None:
        snapshot.assert_match(
            {
                "bob": await api.with_session(bob, review.tags),
                "carol": await api.with_session(carol, review.tags),
                "dave": await api.with_session(dave, review.tags),
            },
            label,
        )

    async with critic_repo.worktree(alice) as worktree:
        async with create_branch(worktree, "branch1") as branch:
            async with worktree.edit("article.md") as created_file:
                print("# Article title", file=created_file)
            await worktree.commit("created article")
            await branch.push()

        async with create_review(critic_repo, alice) as review:
            await review.publish()

            await check_tags("initial")

            async with review.batch_as(bob) as batch:
                raise_for_status(
                    await batch.put(
                        review.path("reviewablefilechanges"),
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee="bob",
                        state="pending",
                    ),
                )
                await check_tags("bob: with draft reviewing")
                raise_for_status(
                    await batch.post("comments", review.issue("Bob does not like!"))
                )
                await check_tags("bob: with draft issue")

            await check_tags("bob: after publish")

            raise_for_status(
                await worktree.execute(
                    "git", "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*"
                )
            )

            raise_for_status(
                await worktree.execute(
                    "git",
                    "branch",
                    "-u",
                    f"refs/remotes/origin/{review.branch.name}",
                )
            )

            async with worktree.edit("article.md") as modified_file:
                print("\nThis is some introductory text.", file=modified_file)
            await worktree.commit("fixup! created article")
            await worktree.push()

            await check_tags("after followup commit")

            async with review.batch_as(carol) as batch:
                raise_for_status(
                    await batch.put(
                        review.path("reviewablefilechanges"),
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee="carol",
                        state="pending",
                    ),
                )
                await check_tags("carol: with draft reviewing")
                raise_for_status(
                    await batch.put(
                        review.path("comments"),
                        {"draft_changes": {"new_state": "resolved"}},
                    )
                )
                await check_tags("carol: with draft resolved issue")

            await check_tags("carol: after publish")
