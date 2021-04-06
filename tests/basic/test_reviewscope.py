import pytest

from ..fixtures.api import API
from ..fixtures.websocket import WebSocket
from ..fixtures.instance import User
from ..fixtures.repository import CriticRepository
from ..fixtures.review import CreateReview
from ..fixtures.branch import CreateBranch
from ..fixtures import Snapshot
from ..utilities import Anonymizer, generate_name, map_to_id, raise_for_status


@pytest.mark.asyncio
async def test_reviewscope(
    websocket: WebSocket,
    api: API,
    critic_repo: CriticRepository,
    admin: User,
    alice: User,
    bob: User,
    carol: User,
    dave: User,
    snapshot: Snapshot,
    anonymizer: Anonymizer,
    create_branch: CreateBranch,
    create_review: CreateReview,
) -> None:
    anonymizer.assert_match(
        raise_for_status(
            await api.get(
                f"repositories/{critic_repo.id}/reviewscopefilters",
                include="reviewscopes",
            )
        ),
        "review scope filters (initial)",
    )

    async with api.session(admin) as as_admin:
        special = await as_admin.create(
            "special", "reviewscopes", {"name": generate_name("special")}
        )
        await as_admin.create(
            "special",
            f"repositories/{critic_repo.id}/reviewscopefilters",
            {"scope": special["id"], "path": "**/*.special", "included": True},
            RepositoryId="$.request.payload.repository",
            ReviewScopeId="$.request.payload.scope",
        )

    anonymizer.assert_match(
        raise_for_status(
            await api.get(
                f"repositories/{critic_repo.id}/reviewscopefilters",
                include="reviewscopes",
            )
        ),
        "review scope filters (final)",
    )

    async with api.session(bob) as as_bob:
        await as_bob.create(
            "bob",
            "repositoryfilters",
            {
                "path": "/",
                "repository": critic_repo.id,
                "scopes": [special["id"]],
                "type": "reviewer",
            },
            RepositoryId="$.request.payload.repository",
            ReviewScopeId="$.request.payload.scopes[*]",
        )

    async with api.session(carol) as as_carol:
        await as_carol.create(
            "carol",
            "repositoryfilters",
            {"path": "/", "repository": critic_repo.id, "type": "reviewer"},
            RepositoryId="$.request.payload.repository",
        )

    async with api.session(dave) as as_dave:
        await as_dave.create(
            "dave",
            "repositoryfilters",
            {
                "path": "/",
                "repository": critic_repo.id,
                "default_scope": False,
                "scopes": [special["id"]],
                "type": "reviewer",
            },
            RepositoryId="$.request.payload.repository",
            ReviewScopeId="$.request.payload.scopes[*]",
        )

    async with critic_repo.worktree(alice) as worktree:
        async with create_branch(worktree, "branch1") as branch:
            async with worktree.edit("created.regular") as regular_file:
                print("created regular file", file=regular_file)
            async with worktree.edit("created.special") as special_file:
                print("created special file", file=special_file)
            await worktree.commit("created files")
            await branch.push()

    async with create_review(critic_repo, alice) as review:
        anonymizer.assert_match(
            raise_for_status(await api.get(f"reviews/{review.id}")), "review (initial)"
        )
        reviewablefilechanges = raise_for_status(
            await api.get(
                f"reviews/{review.id}/reviewablefilechanges",
                include="files,reviewscopes",
            )
        )
        anonymizer.define(
            FileId=map_to_id(reviewablefilechanges.data["linked"]["files"], "path")
        )

        def rfc_name(rfc: dict) -> str:
            file_key = anonymizer.lookup(FileId=rfc["file"])
            assert isinstance(file_key, str)
            if rfc["scope"]:
                scope_key = anonymizer.lookup(ReviewScopeId=rfc["scope"])
                assert isinstance(scope_key, str)
                return f"{file_key}:{scope_key}"
            return f"{file_key}"

        anonymizer.define(
            ReviewableFileChangeId=map_to_id(
                reviewablefilechanges.data["reviewablefilechanges"], rfc_name
            )
        )
        anonymizer.assert_match(
            reviewablefilechanges,
            "reviewable file changes (initial)",
        )

        await review.publish()

        async with api.session(bob) as as_bob:
            anonymizer.assert_match(
                raise_for_status(
                    await as_bob.put(
                        review.path("reviewablefilechanges"),
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee="bob",
                        state="pending",
                    ),
                ),
                "bob: mark all changes as reviewed",
            )
            anonymizer.assert_match(
                raise_for_status(await as_bob.post(review.path("batches"), {})),
                "bob: publish changes",
            )

        async with api.session(carol) as as_carol:
            anonymizer.assert_match(
                raise_for_status(
                    await as_carol.put(
                        review.path("reviewablefilechanges"),
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee="carol",
                        state="pending",
                    ),
                ),
                "carol: mark all changes as reviewed",
            )
            anonymizer.assert_match(
                raise_for_status(await as_carol.post(review.path("batches"), {})),
                "carol: publish changes",
            )

        async with api.session(dave) as as_dave:
            anonymizer.assert_match(
                raise_for_status(
                    await as_dave.put(
                        review.path("reviewablefilechanges"),
                        {"draft_changes": {"new_is_reviewed": True}},
                        assignee="dave",
                        state="pending",
                    ),
                ),
                "dave: mark all changes as reviewed",
            )
            anonymizer.assert_match(
                raise_for_status(await as_dave.post(review.path("batches"), {})),
                "dave: publish changes",
            )

        anonymizer.assert_match(
            raise_for_status(
                await api.get(
                    f"reviews/{review.id}/reviewablefilechanges",
                )
            ),
            "reviewable file changes (final)",
        )
