import asyncio
import json
import logging
import pytest

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures import Snapshot
from ..utilities import Anonymizer, raise_for_status

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_push_branch(
    websocket: WebSocket,
    api: API,
    critic_repo: CriticRepository,
    alice: User,
    snapshot: Snapshot,
    anonymizer: Anonymizer,
) -> None:
    async with critic_repo.worktree(alice) as worktree:
        await worktree.checkout("master", create_branch="branch1")

        async with worktree.edit("readme.txt") as readme:
            print("first", file=readme)
        await worktree.commit("first")

        async with worktree.edit("readme.txt", "a") as readme:
            print("second", file=readme)
        await worktree.commit("second")

        async with worktree.edit("readme.txt", "a") as readme:
            print("third", file=readme)
        await worktree.commit("third")

        snapshot.assert_match(anonymizer(await worktree.push_new()))

        created = await websocket.expect(
            action="created",
            resource_name="branches",
            repository_id=critic_repo.id,
            name="branch1",
        )

        anonymizer.define(BranchId={"branch1": (branch_id := created["object_id"])})

        result = await api.get(f"branches/{branch_id}", include="commits,branchupdates")
        logger.debug(json.dumps(result.to_json(), indent=2))

        snapshot.assert_match(anonymizer(result))

        async with worktree.edit("readme.txt", "a") as readme:
            print("fourth", file=readme)
        await worktree.commit("fourth")

        snapshot.assert_match(anonymizer(await worktree.push()))
        snapshot.assert_match(
            anonymizer(
                await api.get(f"branches/{branch_id}", include="commits,branchupdates")
            )
        )

        async with worktree.edit("readme.txt", "a") as readme:
            print("fourth^2", file=readme)
        await worktree.commit("amended-fourth", amend=True)

        snapshot.assert_match(anonymizer(await worktree.push(force=True)))
        snapshot.assert_match(
            anonymizer(
                await api.get(f"branches/{branch_id}", include="commits,branchupdates")
            )
        )

        # Create a side-branch `branch2` from a commit on `branch1`, and merge
        # the side-branch into `branch1`.
        #
        # Should add all commits on the side-branch to `branch1`.

        await worktree.checkout("branch1~2", create_branch="branch2")

        async with worktree.edit("readme2.txt", "a") as readme2:
            print("side1", file=readme2)
        await worktree.commit("side1")

        await worktree.checkout("branch1")
        raise_for_status(await worktree.execute("git", "merge", "branch2"))
        await worktree.define_sha1("merge-branch1-branch2")

        snapshot.assert_match(anonymizer(await worktree.push()))
        snapshot.assert_match(
            anonymizer(
                await api.get(f"branches/{branch_id}", include="commits,branchupdates")
            )
        )

        # Create a side-branch `branch3` from a commit not on `branch1`, and
        # merge the side-branch into `branch1`.
        #
        # Should add only the merge-commit to `branch1`.

        await worktree.checkout("master", create_branch="branch3")

        async with worktree.edit("readme3.txt", "a") as readme3:
            print("side2", file=readme3)
        await worktree.commit("side2")

        await worktree.checkout("branch1")
        raise_for_status(await worktree.execute("git", "merge", "branch3"))
        await worktree.define_sha1("merge-branch1-branch3")

        snapshot.assert_match(anonymizer(await worktree.push()))
        snapshot.assert_match(
            anonymizer(
                await api.get(f"branches/{branch_id}", include="commits,branchupdates")
            )
        )

        await worktree.checkout("master")

        raise_for_status(await worktree.execute("git", "merge", "--no-ff", "branch1"))
        await worktree.define_sha1("merge-master-branch1")

        snapshot.assert_match(anonymizer(await worktree.push()))

        snapshot.assert_match(
            anonymizer(await api.get(f"branches/{branch_id}", output_format="static"))
        )

        await worktree.checkout("branch1")
        snapshot.assert_match(anonymizer(await worktree.push(delete=True)))

        snapshot.assert_match(
            anonymizer(
                await api.get(f"branches/{branch_id}", output_format="static"),
                masked=[r"$.response.data.error.message:\d+$"],
            )
        )
