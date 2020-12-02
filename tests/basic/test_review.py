import logging
import pytest

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures import Snapshot
from ..utilities import Anonymizer, SetContaining, raise_for_status

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_create_review(
    websocket: WebSocket,
    api: API,
    critic_repo: CriticRepository,
    alice: User,
    bob: User,
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

        anonymizer.assert_match(await worktree.push_new(), "push branch")

        created_branch = await websocket.expect(
            action="created",
            resource_name="branches",
            repository_id=critic_repo.id,
            name="branch1",
        )

        anonymizer.define(
            BranchId={"branch1": (branch_id := created_branch["object_id"])}
        )

        commits = await api.get(f"branches/{branch_id}/commits")
        anonymizer.assert_match(commits, "branch commits")

        created_review = raise_for_status(
            await api.with_session(
                alice,
                lambda api: api.post(
                    "reviews",
                    {
                        "repository": critic_repo.id,
                        "branch": "r/review1",
                        "commits": [commit["id"] for commit in commits.data["commits"]],
                    },
                ),
            )
        )

        anonymizer.define(
            ReviewId={
                "r/review1": (review_id := created_review.data["reviews"][0]["id"])
            }
        )
        snapshot.assert_match(
            anonymizer(
                created_review,
                CommitId="$.request.payload.commits[*]",
                RepositoryId="$.request.payload.repository",
            ),
            "create review",
        )

        await websocket.expect(
            action="created",
            resource_name="reviewevents",
            review_id=review_id,
            event_type="ready",
        )

        ready_review = raise_for_status(
            await api.get(f"reviews/{review_id}", include=["changesets,filechanges"])
        )
        for changeset in ready_review.data["linked"]["changesets"]:
            label = anonymizer.lookup(CommitId=changeset["to_commit"])
            assert isinstance(label, str)
            anonymizer.define(ChangesetId={label: changeset["id"]})
        anonymizer.assert_match(ready_review, "review ready")

        # Changeset completion happens in unpredictable order, so pop all the
        # messages about it. They should all already have arrived, since the
        # "review ready" event has been created.
        for changeset_id in ready_review.data["reviews"][0]["changesets"]:
            message = await websocket.pop_noblock(
                action="modified",
                resource_name="changesets",
                object_id=changeset_id,
                updates=dict(completion_level=SetContaining("full")),
            )
            assert message
            while message:
                message = await websocket.pop_noblock(
                    action="modified",
                    resource_name="changesets",
                    object_id=changeset_id,
                )

        async with api.session(alice) as as_alice:
            snapshot.assert_match(
                anonymizer(
                    raise_for_status(
                        await as_alice.post(
                            f"reviews/{review_id}/reviewfilters",
                            {
                                "subject": bob.id,
                                "type": "reviewer",
                                "path": "",
                            },
                        )
                    ),
                    UserId="$.request.payload.subject",
                ),
                "create review filter",
            )

            anonymizer.assert_match(
                raise_for_status(
                    await as_alice.put(
                        f"reviews/{review_id}",
                        {"state": "open", "summary": "test_review::test_create_review"},
                    )
                ),
                "publish review",
            )

        reviewtags = await api.get("reviewtags")

        for reviewtag in reviewtags.data["reviewtags"]:
            anonymizer.define(ReviewTagId={reviewtag["name"]: reviewtag["id"]})

        async with api.session(bob) as as_bob:
            anonymizer.assert_match(
                raise_for_status(await as_bob.get(f"reviews/{review_id}")),
                "review (as bob)",
            )

            anonymizer.assert_match(
                raise_for_status(
                    await as_bob.get(f"reviews/{review_id}/reviewablefilechanges")
                ),
                "reviewable file changes (as bob)",
            )

            issue_result = raise_for_status(
                await as_bob.post(
                    f"reviews/{review_id}/comments",
                    {"type": "issue", "text": "Add a test, please!"},
                )
            )
            issue_id = issue_result.data["comments"][0]["id"]
            anonymizer.assert_match(
                issue_result,
                "raise issue (as bob)",
            )

            anonymizer.assert_match(
                raise_for_status(
                    await as_bob.put(
                        f"reviews/{review_id}/reviewablefilechanges",
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee=bob.name,
                        state="pending",
                    )
                ),
                "review file changes (as bob)",
            )

            anonymizer.assert_match(
                raise_for_status(
                    await as_bob.post(
                        f"reviews/{review_id}/batches",
                        {"comment": "LGTM"},
                        include="comments,reviews",
                    )
                ),
                "submit changes (as bob)",
            )

        anonymizer.assert_match(
            raise_for_status(await api.get(f"reviews/{review_id}")), "review state"
        )

        anonymizer.assert_match(
            raise_for_status(
                await api.get(f"reviews/{review_id}/batches", include="comments")
            ),
            "review state (batches)",
        )

        async with api.session(alice) as as_alice:
            anonymizer.assert_match(
                raise_for_status(
                    await as_alice.post(
                        f"comments/{issue_id}/replies",
                        {"text": "Will do!"},
                    )
                ),
                "reply to issue (as alice)",
            )
            anonymizer.assert_match(
                raise_for_status(
                    await as_alice.put(
                        f"comments/{issue_id}",
                        {"draft_changes": {"new_state": "resolved"}},
                    )
                ),
                "resolve issue (as alice)",
            )

            anonymizer.assert_match(
                raise_for_status(
                    await as_alice.get(
                        f"reviews/{review_id}", include="batches,comments,replies"
                    )
                ),
                "review state (as alice)",
            )
