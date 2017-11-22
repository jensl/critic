# @users alice, bob

TEST = "039-move-rebase/005-ff-no-overlap-after-rewrite"


def test1(work):
    """Basic fast-forward move rebase with no overlapping work."""

    review = Review(work, "alice", TEST)
    review.addFile(nonsense=f"{TEST}/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit(
        "reference #1", nonsense=content("one", "two", "three"), reference=True
    )
    review.commit("commit #1", nonsense=content("one", "TWO", "three"))
    review.commit("commit #2", nonsense=content("ONE", "TWO", "three"))
    review.submit()

    def commit_ids(sha1s):
        return [review.getCommitId(sha1) for sha1 in sha1s]

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches"},
        expect=partial_json(
            {
                "partitions": review.expected_partitions,
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ]
                },
            }
        ),
    )

    with frontend.signin("alice"):
        history_rewrite_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"history_rewrite": True},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "branchupdate": None,
                "type": "history-rewrite",
            },
        )["id"]

    review.reset()
    review.commit("commit #1 + #2", nonsense=content("ONE", "TWO", "three"))
    review.push(history_rewrite=history_rewrite_id)

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": review.expected_partitions,
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ],
                    "rebases": [
                        {
                            "id": history_rewrite_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "history-rewrite",
                        }
                    ],
                },
            }
        ),
    )

    review.commit(
        "reference #2", nonsense=content("one", "two", "three", "four"), reference=True
    )
    review.push_reference_branch()

    with frontend.signin("alice"):
        move_rebase_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"new_upstream": review.sha1s[-1]},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "branchupdate": None,
                "type": "move",
                "old_upstream": review.getCommitId(review.sha1s[0]),
                "new_upstream": review.getCommitId(
                    review.sha1s[review.last_reference_commit]
                ),
                "equivalent_merge": None,
                "replayed_rebase": None,
            },
        )["id"]

    review.reset()
    review.commit("rebased #1 + #2", nonsense=content("ONE", "TWO", "three", "four"))
    review.push(move_rebase=move_rebase_id)

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": review.expected_partitions,
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ],
                    "rebases": [
                        {
                            "id": history_rewrite_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "history-rewrite",
                        },
                        {
                            "id": move_rebase_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "move",
                            "old_upstream": review.getCommitId(review.sha1s[0]),
                            "new_upstream": review.getCommitId(
                                review.sha1s[review.last_reference_commit]
                            ),
                            "equivalent_merge": int,
                            "replayed_rebase": None,
                        },
                    ],
                },
            }
        ),
    )

    review.commit("commit #3", nonsense=content("ONE", "TWO", "THREE", "four"))
    review.commit("commit #4", nonsense=content("ONE", "TWO", "THREE", "FOUR"))
    review.push()

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": review.expected_partitions,
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ],
                    "rebases": [
                        {
                            "id": history_rewrite_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "history-rewrite",
                        },
                        {
                            "id": move_rebase_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "move",
                            "old_upstream": review.getCommitId(review.sha1s[0]),
                            "new_upstream": review.getCommitId(
                                review.sha1s[review.last_reference_commit]
                            ),
                            "equivalent_merge": int,
                            "replayed_rebase": None,
                        },
                    ],
                },
            }
        ),
    )


with repository.workcopy(clone="small") as work:
    test1(work)
