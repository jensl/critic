# @users alice, bob


def test1(work):
    """Basic fast-forward move rebase with no overlapping work."""

    review = Review(work, "alice", "039-move-rebase/001-ff-no-overlap")
    review.addFile(nonsense="039-move-rebase/001-ff-no-overlap/nonsense.txt")
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
                "partitions": [
                    {"commits": commit_ids(reversed(review.sha1s[-2:])), "rebase": None}
                ],
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

    review.commit(
        "reference #2", nonsense=content("one", "two", "three", "four"), reference=True
    )
    review.push_reference_branch()

    with frontend.signin("alice"):
        rebase_id = frontend.json(
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
    review.commit("rebased #1", nonsense=content("one", "TWO", "three", "four"))
    review.commit("rebased #2", nonsense=content("ONE", "TWO", "three", "four"))
    review.push(move_rebase=True)

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": [], "rebase": rebase_id},
                    {
                        "commits": commit_ids(reversed(review.sha1s[1:3])),
                        "rebase": None,
                    },
                ],
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
                            "id": rebase_id,
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
                        }
                    ],
                },
            }
        ),
    )

    review.commit("commit #3", nonsense=content("ONE", "TWO", "THREE", "four"))
    review.commit("commit #4", nonsense=content("ONE", "TWO", "THREE", "FOUR"))
    review.push()


with repository.workcopy(clone="small") as work:
    test1(work)
