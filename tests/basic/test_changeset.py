import logging
import pytest

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures import Snapshot
from ..utilities import Anonymizer, Blob, SetContaining, raise_for_status

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_changeset(
    websocket: WebSocket,
    api: API,
    critic_repo: CriticRepository,
    alice: User,
    snapshot: Snapshot,
    anonymizer: Anonymizer,
) -> None:
    async with critic_repo.worktree(alice) as worktree:
        await worktree.checkout("master", create_branch="branch1")

        initial = Blob("initial")
        deleted = Blob("deleted")
        added = Blob("added")
        modified = Blob("initial modified")

        anonymizer.define(
            FileSHA1={
                initial.data: initial.sha1,
                deleted.data: deleted.sha1,
                added.data: added.sha1,
                modified.data: modified.sha1,
            }
        )

        async with worktree.edit("modified.txt") as modified_file:
            modified_file.write(initial.data)
        async with worktree.edit("deleted.txt") as deleted_file:
            deleted_file.write(deleted.data)
        await worktree.commit("first")

        async with worktree.edit("added.txt") as added_file:
            added_file.write(added.data)
        async with worktree.edit("modified.txt") as modified_file:
            modified_file.write(modified.data)
        await worktree.delete("deleted.txt")
        await worktree.commit("second")

        anonymizer.assert_match(await worktree.push_new(), "push branch")

        changeset_response = raise_for_status(
            await api.get(
                "changesets",
                commit=await worktree.head_sha1(),
                repository=critic_repo.id,
            )
        )
        changeset = changeset_response.data["changesets"][0]
        anonymizer.define(ChangesetId={"created": (changeset_id := changeset["id"])})
        anonymizer.define(
            CommitId={
                "first": changeset["from_commit"],
                "second": changeset["to_commit"],
            }
        )
        anonymizer.assert_match(
            changeset_response,
            "initial",
            CommitSHA1="$.request.query.commit",
            RepositoryId="$.request.query.repository",
        )

        await websocket.expect(
            resource_name="changesets",
            action="modified",
            object_id=changeset_id,
            updates=dict(completion_level=SetContaining("full")),
        )

        changeset_response = raise_for_status(
            await api.get(
                "changesets",
                commit=await worktree.head_sha1(),
                repository=critic_repo.id,
                include=["files,filechanges"],
            )
        )
        for file in changeset_response.data["linked"]["files"]:
            anonymizer.define(FileId={file["path"]: file["id"]})
        anonymizer.assert_match(
            changeset_response,
            "ready",
            CommitSHA1="$.request.query.commit",
            RepositoryId="$.request.query.repository",
        )
        anonymizer.assert_match(
            raise_for_status(await api.get(f"changesets/{changeset_id}/filediffs")),
            "readable diffs",
        )
        anonymizer.assert_match(
            raise_for_status(
                await api.get(f"changesets/{changeset_id}/filediffs", compact="yes")
            ),
            "compact diffs",
        )
